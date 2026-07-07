"""CLI entry point: evaluate ID classifier and OOD detection performance.

Usage (via DVC or directly)::

    uv run python scripts/evaluate.py \\
        --aot_root          /path/to/aot-dataset \\
        --test_jsonl        data/background_classification/test.jsonl \\
        --corrupted_test_dir data/corrupted_images \\
        --corrupted_val_dir  data/corrupted_images \\
        --corrupted_full_img_dir /path/to/corrupted/full/images \\
        --models_dir        models \\
        --ood_filter        "all:1"
"""

from __future__ import annotations

import csv
import json
import os
from collections import defaultdict
from pathlib import Path

import fire
import mlflow
import numpy as np
import torch
from loguru import logger
from sklearn.metrics import classification_report
from torch.utils.data import DataLoader

from src.ood.common.io import (
    md5_file,
    parse_ood_filter,
    read_jsonl,
    run_name,
    write_jsonl,
)
from src.ood.common.model import build_classifier
from src.ood.common.transforms import CLASSES, make_corrupted_transform, make_eval_transform
from src.ood.preprocessing.corruptions import corrupted_full_path
from src.ood.train.datasets import CorruptedSubset, IDDataset
from src.ood.train.evaluator import auroc_fpr95, predict_loader, score_loader


def _energy_score(logits: torch.Tensor) -> torch.Tensor:
    """Compute the log-sum-exp energy score from class logits.

    Higher values indicate that the input is *more* in-distribution,
    matching the AUROC convention used by ``auroc_fpr95``.

    Args:
        logits: Unnormalised class logit tensor of shape ``(N, C)``.

    Returns:
        1-D energy score tensor of shape ``(N,)``.
    """
    return torch.logsumexp(logits, dim=1)


def _load_model(models_dir: Path, device: str) -> tuple[torch.nn.Module, Path]:
    """Load the energy fine-tuned classifier from the model directory.

    Args:
        models_dir: Directory containing the trained model checkpoint.
        device: PyTorch device string (e.g. ``"cuda"`` or ``"cpu"``).

    Returns:
        A 2-tuple ``(clf, ckpt_path)`` with the loaded model and checkpoint path.

    Raises:
        FileNotFoundError: If the expected checkpoint file is not found.
        RuntimeError: If model loading fails.
    """
    ckpt_path = models_dir / "resnet18_energy.pt"
    clf = build_classifier()
    clf.load_state_dict(torch.load(ckpt_path, map_location=device))
    clf = clf.to(device).eval()
    logger.info(f"Loaded checkpoint: {ckpt_path}")
    return clf, ckpt_path


def _eval_id(
    clf: torch.nn.Module,
    test_jsonl: Path,
    aot_root: Path,
    batch: int,
    num_workers: int,
    device: str,
) -> tuple[np.ndarray, np.ndarray, dict, np.ndarray, list[dict]]:
    """Run in-distribution classification and collect energy scores.

    Args:
        clf: Trained classifier in eval mode.
        test_jsonl: Path to the ID test split JSONL.
        aot_root: Root path to the dataset.
        batch: DataLoader batch size.
        num_workers: DataLoader worker count.
        device: PyTorch device string (e.g. ``"cuda"`` or ``"cpu"``).

    Returns:
        A 5-tuple ``(y_true, y_pred, report_dict, s_id, sample_rows)``.
        *sample_rows* contains per-sample metadata and OOD score fields.
    """
    test_loader = DataLoader(
        IDDataset(test_jsonl, aot_root, make_eval_transform()),
        batch_size=batch,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )
    y_true, y_pred = predict_loader(clf, test_loader, device=device)
    report_str = classification_report(y_true, y_pred, target_names=CLASSES)
    report_dict = classification_report(y_true, y_pred, target_names=CLASSES, output_dict=True)
    logger.info("\n" + report_str)

    s_id = score_loader(lambda x: _energy_score(clf(x)), test_loader, device=device)
    sample_rows = _collect_id_sample_rows(test_loader, y_pred, s_id, aot_root)
    return y_true, y_pred, report_dict, s_id, sample_rows


def _collect_id_sample_rows(
    test_loader: DataLoader,
    y_pred: np.ndarray,
    s_id: np.ndarray,
    aot_root: Path,
) -> list[dict]:
    """Build per-sample rows for ID test records.

    Args:
        test_loader: DataLoader created over ``IDDataset`` with ``shuffle=False``.
        y_pred: Predicted class indices aligned with dataset order.
        s_id: Energy score array aligned with dataset order.
        aot_root: Root path to the AOT dataset.

    Returns:
        List of serialisable per-sample dicts.
    """
    ds = test_loader.dataset
    rows: list[dict] = []
    for i, rec in enumerate(ds.records):
        pred_idx = int(y_pred[i])
        rows.append(
            {
                "task": "background_classification",
                "split": "test",
                "variant": "clean",
                "img_name": rec.get("img_name"),
                "filepath": str((aot_root / rec["path"]).absolute()),
                "source_frame": rec.get("path"),
                "flight_id": rec.get("flight_id"),
                "time": rec.get("time"),
                "background_label_gt": rec["label"],
                "background_label_pred": CLASSES[pred_idx],
                "corruption_type": None,
                "corruption_severity": None,
                "ood_score_energy": float(s_id[i]),
                "ood_label_id_vs_ood": None,
            }
        )
    return rows


def _eval_ood(
    clf: torch.nn.Module,
    s_id: np.ndarray,
    corrupted_test_dir: Path,
    corrupted_full_img_dir: Path,
    batch: int,
    num_workers: int,
    device: str,
) -> tuple[list[dict], np.ndarray, list[dict]]:
    """Evaluate OOD detection per corruption × severity.

    Args:
        clf: Trained classifier in eval mode.
        s_id: Energy scores for the ID test set.
        corrupted_test_dir: Root local directory of corrupted-full manifests
            (``test/dataset.jsonl`` is expected inside).
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        batch: DataLoader batch size.
        num_workers: DataLoader worker count.
        device: PyTorch device string.

    Returns:
        A 3-tuple ``(results, s_ood_all, sample_rows)`` where *results* is a
        list of per-group dicts, *s_ood_all* is the concatenated OOD score
        array, and *sample_rows* contains one row per corrupted sample.
    """
    results: list[dict] = []
    all_s_ood: list[np.ndarray] = []

    test_ood_jsonl = corrupted_test_dir / "test" / "dataset.jsonl"
    if not test_ood_jsonl.exists():
        logger.warning(
            f"Corrupted test JSONL not found at {test_ood_jsonl} — OOD metrics will be empty."
        )
        return results, np.array([]), []

    all_test_recs = read_jsonl(test_ood_jsonl)
    groups: dict[tuple[str, int], list[dict]] = defaultdict(list)
    sample_rows: list[dict] = []
    for r in all_test_recs:
        groups[(r["type"], int(r["severity"]))].append(r)
    for (corruption, sev), sev_recs in sorted(groups.items()):
        ood_ds = CorruptedSubset(sev_recs, corrupted_full_img_dir, make_corrupted_transform())
        ood_loader = DataLoader(
            ood_ds,
            batch_size=batch,
            shuffle=False,
            num_workers=num_workers,
            pin_memory=True,
        )
        s_ood = score_loader(lambda x: _energy_score(clf(x)), ood_loader, device=device)
        y_true_ood, y_pred_ood = predict_loader(clf, ood_loader, device=device)
        all_s_ood.append(s_ood)
        auroc, fpr95 = auroc_fpr95(s_id, s_ood)
        results.append(
            {
                "corruption": corruption,
                "severity": sev,
                "auroc": auroc,
                "fpr95": fpr95,
                "n_ood": len(sev_recs),
            }
        )
        logger.info(f"  {corruption} sev{sev}  AUROC={auroc:.4f}  FPR95={fpr95:.4f}")

        for i, rec in enumerate(sev_recs):
            pred_idx = int(y_pred_ood[i])
            _ = int(y_true_ood[i])  # kept for alignment sanity/readability
            full_path = corrupted_full_path(
                rec["path"], rec["type"], int(rec["severity"]), corrupted_full_img_dir
            )
            sample_rows.append(
                {
                    "task": "background_classification",
                    "split": "test",
                    "variant": f"{corruption}_{sev}",
                    "img_name": rec.get("img_name"),
                    "filepath": str(full_path.absolute()),
                    "source_frame": rec.get("path"),
                    "flight_id": rec.get("flight_id"),
                    "time": rec.get("time"),
                    "background_label_gt": rec["label"],
                    "background_label_pred": CLASSES[pred_idx],
                    "corruption_type": corruption,
                    "corruption_severity": int(sev),
                    "ood_score_energy": float(s_ood[i]),
                    "ood_label_id_vs_ood": None,
                }
            )

    s_ood_all = np.concatenate(all_s_ood) if all_s_ood else np.array([])
    return results, s_ood_all, sample_rows


def _write_per_sample_ood(
    rows: list[dict],
    threshold: float,
    output_dir: Path,
) -> Path:
    """Write per-sample OOD outputs as JSONL.

    Args:
        rows: Sample rows with ``ood_score_energy`` values.
        threshold: Energy threshold at 95%% TPR on validation OOD.
        output_dir: Output directory.

    Returns:
        Path to the written ``ood_per_sample.jsonl`` file.
    """
    for row in rows:
        row["ood_label_id_vs_ood"] = "ID" if row["ood_score_energy"] >= threshold else "OOD"

    path = output_dir / "ood_per_sample.jsonl"
    write_jsonl(path, rows)
    logger.info(f"Per-sample OOD JSONL: {path}")
    return path


def _compute_threshold(
    clf: torch.nn.Module,
    corrupted_val_dir: Path,
    corrupted_full_img_dir: Path,
    batch: int,
    num_workers: int,
    device: str,
) -> float:
    """Compute the energy threshold at 95% TPR on the validation OOD set.

    Args:
        clf: Trained classifier in eval mode.
        corrupted_val_dir: Root local directory of corrupted-full manifests
            (``val/dataset.jsonl`` is expected inside).
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        batch: DataLoader batch size.
        num_workers: DataLoader worker count.
        device: PyTorch device string.

    Returns:
        Scalar threshold value (0.0 if the JSONL is absent).
    """
    val_ood_jsonl = corrupted_val_dir / "val" / "dataset.jsonl"
    if not val_ood_jsonl.exists():
        logger.warning(f"Corrupted val JSONL not found at {val_ood_jsonl} — threshold will be 0.")
        return 0.0
    val_recs = read_jsonl(val_ood_jsonl)
    val_loader = DataLoader(
        CorruptedSubset(val_recs, corrupted_full_img_dir, make_corrupted_transform()),
        batch_size=batch,
        shuffle=False,
        num_workers=num_workers,
        pin_memory=True,
    )
    val_scores = score_loader(lambda x: _energy_score(clf(x)), val_loader, device=device)
    return float(np.quantile(val_scores, 0.95))


def _write_outputs(
    results: list[dict],
    summary: dict,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Write DVC metrics JSON and per-corruption CSV to *output_dir*.

    Args:
        results: Per-corruption × severity result dicts.
        summary: Aggregate metric dict for ``ood_summary.json``.
        output_dir: Output directory.

    Returns:
        A 2-tuple ``(summary_path, csv_path)``.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = output_dir / "ood_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2))
    logger.info(f"DVC metrics: {summary}")

    csv_path = output_dir / "ood_results.csv"
    with open(csv_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["corruption", "severity", "auroc", "fpr95", "n_ood"])
        writer.writeheader()
        writer.writerows(results)
    logger.info(f"Results CSV: {csv_path}")
    return summary_path, csv_path


def _log_mlflow(
    test_jsonl: Path,
    ckpt_path: Path,
    ood_filter: str,
    report_dict: dict,
    results: list[dict],
    summary: dict,
    summary_path: Path,
    csv_path: Path,
) -> None:
    """Log params, metrics, and artefacts to MLflow.

    Args:
        test_jsonl: Path to the ID test JSONL (for MD5 provenance).
        ckpt_path: Path to the model checkpoint (for MD5 provenance).
        ood_filter: OOD filter string logged as a param.
        report_dict: Classification report dict from sklearn.
        results: Per-corruption × severity result dicts.
        summary: Aggregate metric dict.
        summary_path: Path to the written ``ood_summary.json``.
        csv_path: Path to the written ``ood_results.csv``.
    """
    with mlflow.start_run(run_name=run_name("evaluate")):
        mlflow.log_params(
            {
                "test_jsonl_md5": md5_file(test_jsonl),
                "ckpt_md5": md5_file(ckpt_path),
                "ood_filter": ood_filter,
            }
        )
        for cls_name, cls_metrics in report_dict.items():
            if isinstance(cls_metrics, dict):
                for metric_name, value in cls_metrics.items():
                    key = f"cls/{cls_name.replace(' ', '_')}/{metric_name.replace(' ', '_')}"
                    mlflow.log_metric(key, value)
            else:
                mlflow.log_metric(f"cls/{cls_name}", cls_metrics)
        for row in results:
            prefix = f"ood/{row['corruption']}_sev{row['severity']}"
            mlflow.log_metric(f"{prefix}/auroc", row["auroc"])
            mlflow.log_metric(f"{prefix}/fpr95", row["fpr95"])
        mlflow.log_metrics(
            {
                "ood/auroc_mixed": summary["auroc_mixed"],
                "ood/fpr95_mixed": summary["fpr95_mixed"],
                "ood/auroc_mean": summary["auroc_mean"],
                "ood/fpr95_mean": summary["fpr95_mean"],
                "ood/auroc_trained_subset": summary["auroc_trained_subset"],
                "ood/fpr95_trained_subset": summary["fpr95_trained_subset"],
                "ood/threshold": summary["threshold"],
            }
        )
        mlflow.log_artifact(str(summary_path))
        mlflow.log_artifact(str(csv_path))


def evaluate(
    aot_root: str,
    test_jsonl: str,
    corrupted_test_dir: str,
    corrupted_val_dir: str,
    corrupted_full_img_dir: str,
    models_dir: str,
    output_dir: str | None = None,
    ood_filter: str = "all:1",
    ood_filter_file: str | None = None,
    batch: int = 128,
    num_workers: int = 8,
) -> None:
    """Evaluate ID classification accuracy and OOD detection performance.

    Stage 09 of the OOD pipeline.  Loads the trained energy-fine-tuned
    ResNet-18, scores the ID test set (clean full frames) and the corrupted
    test/val sets (corrupted full frames), and writes DVC metrics
    (``ood_summary.json``), a per-corruption CSV, a per-sample OOD JSONL, and
    MLflow run artefacts.

    In addition to aggregate metrics over all corruptions/severities, a
    separate aggregate is computed for the subset matching *ood_filter*
    (the corruptions used during energy fine-tuning) so the user can
    compare in-filter vs. full-set detection performance.

    Args:
        aot_root: Root path to the AOT dataset.
        test_jsonl: Path to the ID test split JSONL.
        corrupted_test_dir: Root local directory of corrupted-full manifests.
            Expected to contain ``test/dataset.jsonl``.
        corrupted_val_dir: Root local directory of corrupted-full manifests.
            Expected to contain ``val/dataset.jsonl`` (threshold calibration).
        corrupted_full_img_dir: Root of the corrupted full-image tree (where
            the corrupted frames generated by stage 05 live).
        models_dir: Directory containing the saved checkpoint
            ``resnet18_energy.pt``.
        output_dir: Directory where output files (``ood_summary.json``,
            ``ood_results.csv``) are written.  Defaults to *models_dir*.
        ood_filter: Comma-separated corruption filter that was used during
            energy fine-tuning, e.g. ``"fog:3,darken:2"`` or ``"all:1"``.
            Overridden by *ood_filter_file* when that file exists.
        ood_filter_file: Optional path to a text file containing the OOD
            filter string (one line).  When provided and the file exists,
            its content overrides *ood_filter*.
        batch: DataLoader batch size.
        num_workers: DataLoader worker count.
    """
    if ood_filter_file is not None:
        p = Path(ood_filter_file)
        if p.exists():
            ood_filter = p.read_text().strip()
            logger.info(f"OOD filter loaded from {p}: {ood_filter}")

    aot_root_p = Path(aot_root)
    test_jsonl_p = Path(test_jsonl)
    corrupted_test_dir_p = Path(corrupted_test_dir)
    corrupted_val_dir_p = Path(corrupted_val_dir)
    corrupted_full_img_dir_p = Path(corrupted_full_img_dir)
    models_dir_p = Path(models_dir)
    output_dir_p = Path(output_dir) if output_dir is not None else models_dir_p

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Device: {device}")

    clf, ckpt_path = _load_model(models_dir_p, device)
    _y_true, _y_pred, report_dict, s_id, id_rows = _eval_id(
        clf,
        test_jsonl_p,
        aot_root_p,
        batch,
        num_workers,
        device,
    )
    results, s_ood_all, ood_rows = _eval_ood(
        clf,
        s_id,
        corrupted_test_dir_p,
        corrupted_full_img_dir_p,
        batch,
        num_workers,
        device,
    )

    auroc_mixed, fpr95_mixed = auroc_fpr95(s_id, s_ood_all) if len(s_ood_all) else (0.0, 1.0)
    auroc_mean = float(np.mean([r["auroc"] for r in results])) if results else 0.0
    fpr95_mean = float(np.mean([r["fpr95"] for r in results])) if results else 1.0

    filt = parse_ood_filter(ood_filter)
    subset_rows = [
        r for r in results if r["corruption"] in filt and r["severity"] >= filt[r["corruption"]]
    ]
    auroc_trained = float(np.mean([r["auroc"] for r in subset_rows])) if subset_rows else 0.0
    fpr95_trained = float(np.mean([r["fpr95"] for r in subset_rows])) if subset_rows else 1.0
    logger.info(
        f"Trained-subset ({ood_filter}): AUROC={auroc_trained:.4f}  FPR95={fpr95_trained:.4f}"
    )

    threshold = _compute_threshold(
        clf, corrupted_val_dir_p, corrupted_full_img_dir_p, batch, num_workers, device
    )

    summary = {
        "auroc_mixed": auroc_mixed,
        "fpr95_mixed": fpr95_mixed,
        "auroc_mean": auroc_mean,
        "fpr95_mean": fpr95_mean,
        "auroc_trained_subset": auroc_trained,
        "fpr95_trained_subset": fpr95_trained,
        "ood_filter": ood_filter,
        "threshold": threshold,
    }
    summary_path, csv_path = _write_outputs(results, summary, output_dir_p)
    _write_per_sample_ood(id_rows + ood_rows, threshold, output_dir_p)

    mlflow.set_tracking_uri(os.environ.get("MLFLOW_TRACKING_URI", "http://localhost:5000"))
    mlflow.set_experiment("daa_ood_detector")
    _log_mlflow(
        test_jsonl_p, ckpt_path, ood_filter, report_dict, results, summary, summary_path, csv_path
    )

    logger.info("Evaluation complete.")


if __name__ == "__main__":
    fire.Fire(evaluate)
