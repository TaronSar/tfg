"""CLI: train the few-shot UAV identification encoder (MLflow-tracked).

Following the department convention, this script owns the CLI (``fire``) and the
MLflow orchestration; the training logic lives in ``src.uavid.train.trainer``.

Usage (via DVC or directly)::

    PYTHONPATH=. uv run python scripts/train.py \\
        --data_root data/04_dataset \\
        --support_split enrollment \\
        --n_way 15 --test_n_way 5 --k_shot_range "1,3,5,10,15" --degrade_p 0.0
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import fire
import mlflow
from loguru import logger

from src.uavid.common.config_loader import load_mlflow_config
from src.uavid.common.io import md5_file, run_name
from src.uavid.common.transforms import build_transform
from src.uavid.dataset import IdentityIndex
from src.uavid.model import BACKBONE_NORM
from src.uavid.train import train_protonet

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # python-dotenv is optional
    pass


def _log_artifacts(out_dir: Path, best_acc: float, history: list[dict],
                   embed_dim: int, image_size: int) -> None:
    """Log checkpoints, manifest and training history to MLflow.

    Args:
        out_dir: Directory holding ``best.pth`` / ``last.pth``.
        best_acc: Best validation accuracy reached.
        history: Per-epoch metric dicts.
        embed_dim: Embedding dimensionality of the trained encoder.
        image_size: Encoder input resolution.
    """
    best_path = out_dir / "best.pth"
    last_path = out_dir / "last.pth"

    # Manifest with the headline metric + DVC-compatible hashes for traceability.
    manifest = {
        "best_val_acc": best_acc,
        "embed_dim": embed_dim,
        "image_size": image_size,
        "backbone": backbone,
        "epochs_run": len(history),
    }
    if best_path.exists():
        manifest["best_pth_md5"] = md5_file(best_path)
    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))

    history_path = out_dir / "history.json"
    history_path.write_text(json.dumps(history, indent=2))

    for p in (best_path, last_path, manifest_path, history_path):
        if p.exists():
            mlflow.log_artifact(str(p), artifact_path="checkpoints")


def main(
    data_root: str,
    out: str = "models/00_train",
    epochs: int = 50,
    episodes_per_epoch: int = 200,
    val_episodes: int = 100,
    n_way: int = 15,
    test_n_way: int = 5,
    k_shot: int = 5,
    k_shot_range: str | None = "1,3,5,10,15",
    q_query: int = 5,
    lr: float = 1e-3,
    backbone_lr: float = 1e-4,
    image_size: int = 224,
    embed_dim: int = 128,
    metric: str = "euclidean",
    no_l2norm: bool = False,
    degrade_p: float = 0.0,
    support_split: str | None = "enrollment",
    freeze_backbone_epochs: int = 2,
    backbone: str = "mobilenetv3",
    exclude_json: str | None = None,
    seed: int = 42,
    mlflow_tracking: bool = True,
) -> None:
    """Train the encoder and log the run to MLflow.

    Args:
        data_root: Dataset root containing ``train/``, ``val/`` and optionally
            the ``support_split`` directory.
        out: Output directory for ``best.pth`` / ``last.pth``.
        epochs ... freeze_backbone_epochs: Episodic hyperparameters.
        k_shot_range: Comma-separated shots for shot-robust sampling (or None).
        backbone: Feature backbone.  Choices: ``mobilenetv3`` (default),
            ``dinov2_vits14``, ``dinov2_vitb14``, ``clip_vit_b32``.  DINOv2 /
            CLIP backbones download weights (~330-350 MB) on first use.
        no_l2norm: Disable final L2-normalisation (unnormalised ablation).
        seed: RNG seed.
        mlflow_tracking: Log the run to MLflow when True.
    """
    import random

    import numpy as np
    import torch

    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")
    normalize = not no_l2norm
    shots: list[int] | None
    if k_shot_range is None:
        shots = None
    elif isinstance(k_shot_range, (list, tuple)):
        shots = [int(x) for x in k_shot_range]
    else:
        shots = [int(x) for x in str(k_shot_range).split(",")]

    excluded: set[str] = set()
    if exclude_json:
        from src.uavid.preprocessing.filter_crops import load_excluded

        excluded = load_excluded(exclude_json)
        logger.info(f"Loaded {len(excluded)} excluded crops from {exclude_json}")
    ex_root = Path(data_root)

    train_index = IdentityIndex(Path(data_root) / "train", exclude=excluded, exclude_root=ex_root)
    val_index = IdentityIndex(Path(data_root) / "val", exclude=excluded, exclude_root=ex_root)
    support_index = (IdentityIndex(Path(data_root) / support_split, exclude=excluded, exclude_root=ex_root)
                     if support_split else None)
    logger.info(f"Train: {train_index.stats()}")
    logger.info(f"Val:   {val_index.stats()}")
    if support_index:
        logger.info(f"Support ({support_split}): {support_index.stats()}")

    train_tfm = build_transform(image_size, train=True, degrade_p=degrade_p,
                                mean=BACKBONE_NORM[backbone][0],
                                std=BACKBONE_NORM[backbone][1])
    val_tfm = build_transform(image_size, train=False,
                              mean=BACKBONE_NORM[backbone][0],
                              std=BACKBONE_NORM[backbone][1])
    support_tfm = (build_transform(image_size, train=False,
                                   mean=BACKBONE_NORM[backbone][0],
                                   std=BACKBONE_NORM[backbone][1])
                   if support_index else None)

    params = {
        "epochs": epochs, "episodes_per_epoch": episodes_per_epoch,
        "n_way": n_way, "test_n_way": test_n_way, "k_shot": k_shot,
        "k_shot_range": k_shot_range, "q_query": q_query, "lr": lr,
        "backbone_lr": backbone_lr, "image_size": image_size,
        "embed_dim": embed_dim, "metric": metric, "l2_normalize": normalize,
        "degrade_p": degrade_p, "support_split": support_split,
        "freeze_backbone_epochs": freeze_backbone_epochs, "device": device,
        "n_train_identities": len(train_index), "n_val_identities": len(val_index),
        "backbone": backbone,
    }

    cfg = load_mlflow_config()
    tracking_uri = os.environ.get("MLFLOW_TRACKING_URI", cfg.get("tracking_uri"))
    experiment = os.environ.get("MLFLOW_EXPERIMENT_NAME", cfg.get("experiment_name"))

    active = False
    if mlflow_tracking:
        try:
            mlflow.set_tracking_uri(tracking_uri)
            mlflow.set_experiment(experiment)
            # Build a human-readable run name: <dataset>_<YYYYMMDD_HHMMSS>
            from datetime import datetime
            dataset_slug = Path(data_root).name
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            mlflow.start_run(run_name=f"{dataset_slug}_{ts}")
            mlflow.log_params(params)
            mlflow.set_tags({"task": "few_shot_uav_identification", "data_root": data_root})
            active = True
            logger.info(f"MLflow: logging to {tracking_uri} / {experiment}")
        except Exception as e:  # network-dependent
            logger.warning(f"MLflow disabled (start failed): {e}")

    def _on_epoch(epoch: int, metrics: dict) -> None:
        if active:
            try:
                mlflow.log_metrics(
                    {k: float(v) for k, v in metrics.items()
                     if isinstance(v, (int, float))}, step=epoch)
            except Exception as e:
                logger.warning(f"MLflow metric logging failed: {e}")

    try:
        best_acc, history = train_protonet(
            train_index=train_index, val_index=val_index,
            train_tfm=train_tfm, val_tfm=val_tfm,
            support_index=support_index, support_tfm=support_tfm,
            out_dir=Path(out), epochs=epochs,
            episodes_per_epoch=episodes_per_epoch, val_episodes=val_episodes,
            n_way=n_way, test_n_way=test_n_way, k_shot=k_shot,
            k_shot_range=shots, q_query=q_query, lr=lr, backbone_lr=backbone_lr,
            embed_dim=embed_dim, image_size=image_size, metric=metric,
            normalize=normalize, degrade_p=degrade_p, support_split=support_split,
            freeze_backbone_epochs=freeze_backbone_epochs, backbone=backbone,
            device=device, on_epoch=_on_epoch,
        )
        if active:
            mlflow.set_tags({"best_val_acc": f"{best_acc:.4f}"})
            _log_artifacts(Path(out), best_acc, history, embed_dim, image_size)
    finally:
        if active:
            mlflow.end_run()


if __name__ == "__main__":
    fire.Fire(main)
