"""CLI entry point: train ID classifier + energy fine-tuning.

Usage (via DVC or directly)::

    uv run python scripts/train.py \\
        --aot_root /path/to/aot-dataset \\
        --train_jsonl data/background_classification/train.jsonl \\
        --val_jsonl   data/background_classification/val.jsonl \\
        --corrupted_train_dir data/corrupted_images \\
        --corrupted_full_img_dir /path/to/corrupted/full/images \\
        --models_dir  models \\
        --ood_filter  "all:1"
"""

from __future__ import annotations

import json
import os
import random
from pathlib import Path

import fire
import mlflow
import mlflow.onnx
import mlflow.pytorch
import numpy as np
import onnx as onnx_lib
import torch
import torchvision
from loguru import logger
from torch.utils.data import DataLoader

from src.ood.common.io import (
    filter_ood_records,
    md5_file,
    parse_ood_filter,
    read_jsonl,
    run_name,
)
from src.ood.common.model import build_classifier
from src.ood.common.transforms import (
    make_corrupted_transform,
    make_eval_transform,
    make_train_transform,
)
from src.ood.train.datasets import CorruptedSubset, IDDataset
from src.ood.train.trainer import energy_finetune, train_classifier


def _seed_everything(seed: int) -> None:
    """Seed all relevant random number generators for reproducibility.

    Args:
        seed: Integer seed value.
    """
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def _load_ood_records(corrupted_train_dir: Path, ood_filter: str) -> list[dict]:
    """Read and filter corrupted training records according to *ood_filter*.

    Args:
        corrupted_train_dir: Root directory of the corrupted image output.
            ``train/dataset.jsonl`` is expected inside.
        ood_filter: Filter string, e.g. ``"fog:3,darken:2"`` or ``"all:1"``.

    Returns:
        Filtered list of JSONL records, or an empty list if the JSONL is absent.
    """
    ood_jsonl = corrupted_train_dir / "train" / "dataset.jsonl"
    filt = parse_ood_filter(ood_filter)
    if not ood_jsonl.exists():
        logger.warning(
            f"Corrupted training JSONL not found at {ood_jsonl} "
            "— energy fine-tuning will be skipped."
        )
        return []
    all_ood = read_jsonl(ood_jsonl)
    records = filter_ood_records(all_ood, filt)
    logger.info(f"OOD filter: {ood_filter}  →  {len(records):,}/{len(all_ood):,} records kept")
    return records


def _build_loaders(
    train_jsonl: Path,
    val_jsonl: Path,
    aot_root: Path,
    ood_records: list[dict],
    corrupted_train_dir: Path,
    corrupted_full_img_dir: Path,
    batch: int,
    num_workers: int,
) -> tuple[DataLoader, DataLoader, DataLoader | None, DataLoader | None]:
    """Build DataLoaders for the ID train/val splits and the OOD subsets.

    Args:
        train_jsonl: Path to the training JSONL split.
        val_jsonl: Path to the validation JSONL split.
        aot_root: Root path to the AOT dataset.
        ood_records: Filtered OOD records; if empty, OOD loaders are ``None``.
        corrupted_train_dir: Root local directory of the corrupted-full
            manifests (``train/`` and ``val/`` ``dataset.jsonl`` files).
        corrupted_full_img_dir: Root of the corrupted full-image tree (where
            the actual corrupted frames live).
        batch: DataLoader batch size.
        num_workers: DataLoader worker count.

    Returns:
        A 4-tuple ``(train_loader, val_loader, ood_loader, ood_val_loader)``.
        *ood_loader* and *ood_val_loader* are ``None`` when *ood_records* is
        empty or the corresponding JSONL is absent.
    """
    train_loader = DataLoader(
        IDDataset(train_jsonl, aot_root, make_train_transform()),
        batch_size=batch,
        shuffle=True,
        num_workers=num_workers,
        pin_memory=True,
    )
    val_loader = DataLoader(
        IDDataset(val_jsonl, aot_root, make_eval_transform()),
        batch_size=batch,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )
    ood_loader: DataLoader | None = None
    ood_val_loader: DataLoader | None = None
    if ood_records:
        ood_loader = DataLoader(
            CorruptedSubset(
                ood_records,
                corrupted_full_img_dir,
                make_corrupted_transform(),
            ),
            batch_size=batch,
            shuffle=True,
            num_workers=num_workers,
            pin_memory=True,
        )
        ood_val_jsonl = corrupted_train_dir / "val" / "dataset.jsonl"
        if ood_val_jsonl.exists():
            ood_val_records = filter_ood_records(
                read_jsonl(ood_val_jsonl),
                parse_ood_filter("all:1"),
            )
            ood_val_loader = DataLoader(
                CorruptedSubset(
                    ood_val_records,
                    corrupted_full_img_dir,
                    make_corrupted_transform(),
                ),
                batch_size=batch,
                shuffle=False,
                num_workers=num_workers,
                pin_memory=True,
            )
        else:
            logger.warning(
                "OOD val JSONL not found at {} — energy gap metrics will be skipped.",
                ood_val_jsonl,
            )
    return train_loader, val_loader, ood_loader, ood_val_loader


def _run_id_stage(
    train_loader: DataLoader,
    val_loader: DataLoader,
    clf_path: Path,
    epochs: int,
    lr: float,
    weight_decay: float,
    device: str,
    freeze_backbone: bool = True,
    early_stopping_patience: int = 0,
) -> tuple[torch.nn.Module, float]:
    """Train the ID classifier and save its checkpoint.

    Args:
        train_loader: DataLoader for the ID training split.
        val_loader: DataLoader for the ID validation split.
        clf_path: Destination path for the saved state dict.
        epochs: Number of training epochs.
        lr: AdamW learning rate.
        weight_decay: AdamW weight decay.
        device: PyTorch device string.
        freeze_backbone: Whether to freeze backbone layers during training.
        early_stopping_patience: Stop training when val_loss does not improve
            for this many consecutive epochs.  ``0`` disables early stopping.

    Returns:
        A 2-tuple ``(clf, best_val_acc)``.
    """
    logger.info("Stage 1: ID classification fine-tuning …")
    clf, best_val_acc, history = train_classifier(
        build_classifier(freeze=freeze_backbone),
        train_loader,
        val_loader,
        epochs=epochs,
        lr=lr,
        weight_decay=weight_decay,
        label="resnet18",
        device=device,
        early_stopping_patience=early_stopping_patience,
    )
    for epoch_i, (tl, vl, ta, va) in enumerate(
        zip(
            history["train_loss"],
            history["val_loss"],
            history["train_acc"],
            history["val_acc"],
            strict=True,
        ),
        start=1,
    ):
        mlflow.log_metrics(
            {"train_loss": tl, "val_loss": vl, "train_acc": ta, "val_acc": va},
            step=epoch_i,
        )
    mlflow.log_metric("best_val_acc", best_val_acc)
    torch.save(clf.state_dict(), clf_path)
    return clf, best_val_acc


def _run_energy_stage(
    clf: torch.nn.Module,
    train_loader: DataLoader,
    val_loader: DataLoader,
    ood_loader: DataLoader | None,
    ood_val_loader: DataLoader | None,
    energy_path: Path,
    epochs_energy: int,
    lr_energy: float,
    weight_decay: float,
    energy_alpha: float,
    energy_margin_in: float,
    energy_margin_out: float,
    min_val_acc: float,
    device: str,
) -> torch.nn.Module:
    """Apply energy fine-tuning and save the resulting checkpoint.

    Args:
        clf: Pre-trained ID classifier.
        train_loader: DataLoader for the ID training split.
        val_loader: DataLoader for the ID validation split.
        ood_loader: DataLoader for the OOD training subset, or ``None`` to skip.
        ood_val_loader: DataLoader for the OOD validation subset, or ``None``
            to skip energy gap tracking.
        energy_path: Destination path for the saved state dict.
        epochs_energy: Number of energy fine-tuning epochs.
        lr_energy: AdamW learning rate for the energy stage.
        weight_decay: AdamW weight decay.
        energy_alpha: Weight of the energy regularisation term.
        energy_margin_in: Energy margin target for in-distribution samples.
        energy_margin_out: Energy margin target for OOD samples.
        min_val_acc: Minimum ID validation accuracy required for a checkpoint
            to be considered during energy fine-tuning.
        device: PyTorch device string.

    Returns:
        Energy fine-tuned classifier (or the original *clf* if skipped).
    """
    if ood_loader is None:
        logger.warning("No corrupted OOD data found — skipping energy fine-tuning.")
        torch.save(clf.state_dict(), energy_path)
        return clf
    logger.info("Stage 2: Energy fine-tuning …")
    clf_energy, e_history = energy_finetune(
        clf,
        train_loader,
        ood_loader,
        val_loader,
        ood_val_loader if ood_val_loader is not None else val_loader,
        n_epochs=epochs_energy,
        lr=lr_energy,
        weight_decay=weight_decay,
        energy_alpha=energy_alpha,
        energy_margin_in=energy_margin_in,
        energy_margin_out=energy_margin_out,
        min_val_acc=min_val_acc,
        label="resnet18",
        device=device,
    )
    for ep_i, (el, va, ei, eo) in enumerate(
        zip(
            e_history["energy_loss"],
            e_history["val_acc"],
            e_history["energy_id_mean"],
            e_history["energy_ood_mean"],
            strict=True,
        ),
        start=1,
    ):
        mlflow.log_metrics(
            {
                "energy_loss": el,
                "energy_val_acc": va,
                "energy_id_mean": ei,
                "energy_ood_mean": eo,
                "energy_gap": ei - eo,
            },
            step=ep_i,
        )
    torch.save(clf_energy.state_dict(), energy_path)
    return clf_energy


def _export_onnx(clf: torch.nn.Module, onnx_path: Path, device: str) -> None:
    """Export *clf* to ONNX opset 18.

    Args:
        clf: Model to export (set to eval mode internally).
        onnx_path: Destination ``.onnx`` file path.
        device: PyTorch device string used to create the dummy input.
    """
    clf.eval()
    torch.onnx.export(
        clf,
        torch.zeros(1, 3, 224, 224, device=device),
        str(onnx_path),
        dynamo=False,
        opset_version=18,
        input_names=["image"],
        output_names=["logits"],
    )
    logger.info(f"ONNX exported: {onnx_path}")


def _log_artifacts(
    clf_energy: torch.nn.Module,
    clf_path: Path,
    energy_path: Path,
    onnx_path: Path,
    models_dir: Path,
    best_val_acc: float,
) -> None:
    """Write manifest and register models in the MLflow Model Registry.

    Args:
        clf_energy: Energy fine-tuned classifier.
        clf_path: Path to the ID classifier checkpoint.
        energy_path: Path to the energy checkpoint.
        onnx_path: Path to the ONNX export.
        models_dir: Directory where ``manifest.json`` is written.
        best_val_acc: Best validation accuracy from the ID stage.
    """
    manifest_path = models_dir / "manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "best_val_acc": best_val_acc,
                "classifier_md5": md5_file(clf_path),
                "energy_md5": md5_file(energy_path),
                "onnx_md5": md5_file(onnx_path),
            },
            indent=2,
        )
    )
    mlflow.log_artifact(str(clf_path))
    mlflow.log_artifact(str(manifest_path))
    pip_reqs = [
        f"torch=={torch.__version__}",
        f"torchvision=={torchvision.__version__}",
        "--extra-index-url https://download.pytorch.org/whl/cu124",
    ]
    mlflow.pytorch.log_model(
        clf_energy.cpu(),
        name="pytorch_model",
        registered_model_name="resnet18_energy",
        pip_requirements=pip_reqs,
    )
    mlflow.onnx.log_model(
        onnx_lib.load(str(onnx_path)),
        name="onnx_model",
        registered_model_name="resnet18_energy_onnx",
    )


def train(
    aot_root: str,
    train_jsonl: str,
    val_jsonl: str,
    corrupted_train_dir: str,
    corrupted_full_img_dir: str,
    models_dir: str,
    ood_filter: str = "all:1",
    ood_filter_file: str | None = None,
    batch: int = 128,
    num_workers: int = 8,
    epochs: int = 12,
    epochs_energy: int = 10,
    lr: float = 0.0003,
    lr_energy: float = 0.0001,
    weight_decay: float = 0.0001,
    energy_alpha: float = 0.2,
    energy_margin_in: float = -25.0,
    energy_margin_out: float = -5.0,
    min_val_acc: float = 0.98,
    seed: int = 0,
    freeze_backbone: bool = True,
    early_stopping_patience: int = 2,
) -> None:
    """Train ResNet-18 ID classifier, then apply energy-regularised OOD fine-tuning.

    Stage 04 of the OOD pipeline.  Trains a ResNet-18 classifier on AOT
    background frames, optionally fine-tunes with corrupted OOD images using
    energy regularisation, exports the final model to ONNX, and logs all
    metrics and artefacts to MLflow.

    All hyperparameter defaults are loaded from dvc_config.yaml. Override
    any parameter by passing it explicitly.

    Args:
        aot_root: Root path to the AOT dataset.
        train_jsonl: Path to the training JSONL split.
        val_jsonl: Path to the validation JSONL split.
        corrupted_train_dir: Root local directory of the corrupted-full
            manifests (e.g. ``data/05_create_corrupted_full``).  The
            ``train/dataset.jsonl`` and ``val/dataset.jsonl`` files are
            expected inside.
        corrupted_full_img_dir: Root of the corrupted full-image tree (where
            the actual corrupted frames generated by stage 05 live).
        models_dir: Output directory for saved checkpoints and ONNX model.
        ood_filter: Comma-separated corruption filter for energy fine-tuning,
            e.g. ``"fog:3,darken:2"`` or ``"all:1"`` (default from config).
            Only corrupted images matching the filter are used as OOD exposure.
            Overridden by *ood_filter_file* when that file exists.
        ood_filter_file: Optional path to a text file containing the OOD
            filter string (one line).  When provided and the file exists,
            its content overrides *ood_filter*.
        batch: DataLoader batch size.
        num_workers: DataLoader worker count.
        epochs: Number of ID classification training epochs.
        epochs_energy: Number of energy fine-tuning epochs.
        lr: AdamW learning rate for the ID stage.
        lr_energy: AdamW learning rate for the energy fine-tuning stage.
        weight_decay: AdamW weight decay.
        energy_alpha: Weight of the energy regularisation term.
        energy_margin_in: Energy margin target for in-distribution samples.
        energy_margin_out: Energy margin target for OOD samples.
        min_val_acc: Minimum ID validation accuracy required for a checkpoint
            to be considered during energy fine-tuning.  Guards against
            catastrophic forgetting.
        seed: Random seed for reproducibility.
        freeze_backbone: When ``True`` (default), only ``layer3``, ``layer4``,
            and ``fc`` are trainable.  Set to ``False`` to fine-tune the full
            network.
        early_stopping_patience: Stop ResNet training when val_loss does not
            improve for this many consecutive epochs.
    """
    logger.info(
        f"Training config: batch={batch}, num_workers={num_workers}, epochs={epochs}"
    )

    if ood_filter_file is not None:
        p = Path(ood_filter_file)
        if p.exists():
            ood_filter = p.read_text().strip()
            logger.info(f"OOD filter loaded from {p}: {ood_filter}")

    _seed_everything(seed)

    aot_root_p = Path(aot_root)
    train_jsonl_p = Path(train_jsonl)
    val_jsonl_p = Path(val_jsonl)
    corrupted_train_dir_p = Path(corrupted_train_dir)
    corrupted_full_img_dir_p = Path(corrupted_full_img_dir)
    models_dir_p = Path(models_dir)
    models_dir_p.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")

    ood_records = _load_ood_records(corrupted_train_dir_p, ood_filter)
    train_loader, val_loader, ood_loader, ood_val_loader = _build_loaders(
        train_jsonl_p,
        val_jsonl_p,
        aot_root_p,
        ood_records,
        corrupted_train_dir_p,
        corrupted_full_img_dir_p,
        batch,
        num_workers,
    )

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("daa_ood_detector")

    with mlflow.start_run(run_name=run_name("resnet18_energy_ft")):
        mlflow.log_params(
            {
                "batch": batch,
                "num_workers": num_workers,
                "epochs": epochs,
                "epochs_energy": epochs_energy,
                "lr": lr,
                "lr_energy": lr_energy,
                "weight_decay": weight_decay,
                "energy_alpha": energy_alpha,
                "energy_margin_in": energy_margin_in,
                "energy_margin_out": energy_margin_out,
                "min_val_acc": min_val_acc,
                "ood_filter": ood_filter,
                "seed": seed,
                "device": device,
                "freeze_backbone": freeze_backbone,
                "early_stopping_patience": early_stopping_patience,
                "train_jsonl_md5": md5_file(train_jsonl_p),
                "val_jsonl_md5": md5_file(val_jsonl_p),
            }
        )

        clf_path = models_dir_p / "resnet18_classifier.pt"
        clf, best_val_acc = _run_id_stage(
            train_loader,
            val_loader,
            clf_path,
            epochs,
            lr,
            weight_decay,
            device,
            freeze_backbone,
            early_stopping_patience,
        )

        energy_path = models_dir_p / "resnet18_energy.pt"
        clf_energy = _run_energy_stage(
            clf,
            train_loader,
            val_loader,
            ood_loader,
            ood_val_loader,
            energy_path,
            epochs_energy,
            lr_energy,
            weight_decay,
            energy_alpha,
            energy_margin_in,
            energy_margin_out,
            min_val_acc,
            device,
        )

        onnx_path = models_dir_p / "resnet18_energy.onnx"
        _export_onnx(clf_energy, onnx_path, device)

        _log_artifacts(clf_energy, clf_path, energy_path, onnx_path, models_dir_p, best_val_acc)

    logger.info("Training complete.")


if __name__ == "__main__":
    fire.Fire(train)
