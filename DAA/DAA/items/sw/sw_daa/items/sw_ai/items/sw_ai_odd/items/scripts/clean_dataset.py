"""CLI entry point: audit classification dataset with automated data quality tools.

Runs data quality auditing (Cleanlab Datalab) on each split to detect
label errors, outliers, near-duplicates, class imbalance and non-IID issues.
All splits are passed through unchanged, there is no automatic removal. Reports are
generated for human review via FiftyOne and stored as JSON artifacts.

Usage (via DVC or directly)::

    uv run python scripts/clean_dataset.py \\
        --aot_root /path/to/dataset \\
        --input_dir data/01_create_dataset \\
        --output_dir data/02_audit_dataset
"""
from __future__ import annotations

import json
from pathlib import Path

import fire
import numpy as np
import torch
from loguru import logger
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_predict

from src.ood.cleaning.auditor import generate_report, run_datalab_audit
from src.ood.cleaning.embeddings import compute_dinov2_embeddings
from src.ood.cleaning.fiftyone_audit import build_and_audit
from src.ood.common.config_loader import load_fiftyone_dataset_name
from src.ood.common.constants import SPLIT_NAMES
from src.ood.common.io import read_jsonl, write_jsonl
from src.ood.common.path_utils import image_path, parse_frame_path
from src.ood.common.transforms import CLASSES


def _resolve_image_paths(records: list[dict], aot_root: Path) -> list[Path]:
    """Build absolute image paths from JSONL records.

    ``part`` is read from the ``part`` field when present; otherwise it is
    parsed from the ``path`` field (first path component) to stay compatible
    with records produced by both code paths in ``create_dataset.py``.

    Args:
        records: List of JSONL dicts containing at minimum ``flight_id``,
            ``img_name``, and ``path`` keys.
        aot_root: Root path to the AOT dataset.

    Returns:
        List of absolute ``Path`` objects, one per record.
    """
    paths = []
    for r in records:
        part = r.get("part") or parse_frame_path(r["path"])[2]
        paths.append(image_path(r["flight_id"], r["img_name"], part, aot_root))
    return paths


def _write_report(report: dict, output_dir: Path, split_name: str) -> None:
    """Serialise a Cleanlab audit report to a JSON file.

    Args:
        report: Report dict produced by
            :func:`~src.ood.cleaning.auditor.generate_report`.
        output_dir: Directory where the report file is written.
        split_name: Split identifier used in the filename
            (e.g. ``"train"`` → ``train_cleanlab_report.json``).
    """
    path = output_dir / f"{split_name}_cleanlab_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    logger.info(f"Wrote report → {path}")


def _load_splits(input_dir: Path) -> dict[str, list[dict]]:
    """Load train/val/test JSONL splits from *input_dir*.

    Args:
        input_dir: Directory containing ``train.jsonl``, ``val.jsonl``,
            and ``test.jsonl``.

    Returns:
        Dict mapping split name to its list of JSONL records.
    """
    splits: dict[str, list[dict]] = {}
    for name in SPLIT_NAMES:
        path = input_dir / f"{name}.jsonl"
        splits[name] = read_jsonl(path)
        logger.info(f"Loaded {name}: {len(splits[name])} records")
    return splits


def _compute_all_embeddings(
    splits: dict[str, list[dict]],
    aot_root: Path,
    model_name: str,
    batch_size: int,
    device: str,
) -> dict[str, np.ndarray]:
    """Compute embeddings for every image across all splits.

    Images from all splits are batched together in a single forward-pass
    run for efficiency, then sliced back into per-split arrays.

    Args:
        splits: Dict mapping split name to JSONL records.
        aot_root: Root path to the AOT dataset on NAS.
        model_name: ``timm`` model identifier for the backbone.
        batch_size: Inference batch size.
        device: PyTorch device string.

    Returns:
        Dict mapping split name to its embedding array of shape
        ``(N_split, embed_dim)``.
    """
    all_records = splits["train"] + splits["val"] + splits["test"]
    all_paths = _resolve_image_paths(all_records, aot_root)

    logger.info(f"Computing embeddings for {len(all_paths)} images …")
    all_embeddings = compute_dinov2_embeddings(
        all_paths, model_name=model_name, batch_size=batch_size, device=device,
    )

    idx = 0
    emb: dict[str, np.ndarray] = {}
    for name in SPLIT_NAMES:
        n = len(splits[name])
        emb[name] = all_embeddings[idx : idx + n]
        idx += n
    return emb


def _save_embeddings(
    emb: dict[str, np.ndarray],
    output_dir: Path,
) -> None:
    """Persist per-split embedding arrays as ``.npy`` files.

    Args:
        emb: Dict mapping split name to embedding array.
        output_dir: Directory where ``.npy`` files are saved.
    """
    for name in SPLIT_NAMES:
        emb_path = output_dir / f"embeddings_{name}.npy"
        np.save(emb_path, emb[name])
        logger.info(f"Saved {emb_path} — shape {emb[name].shape}")


def _compute_pred_probs(
    emb: dict[str, np.ndarray],
    train_records: list[dict],
    cv_folds: int,
    seed: int,
) -> dict[str, np.ndarray]:
    """Compute prediction probabilities for all splits.

    The training set uses cross-validated (out-of-sample) probabilities
    to avoid data leakage.  Val/test splits use direct inference from a
    classifier fitted on the full training set.

    Args:
        emb: Dict mapping split name to embedding array.
        train_records: JSONL records for the training split (used to
            extract integer labels).
        cv_folds: Number of cross-validation folds.
        seed: Random seed for the classifier and cross-validation.

    Returns:
        Dict mapping split name to a ``pred_probs`` array of shape
        ``(N_split, num_classes)``.
    """
    class_to_idx = {c: i for i, c in enumerate(CLASSES)}
    train_labels_int = np.array([class_to_idx[r["label"]] for r in train_records])

    n_splits = min(cv_folds, len(np.unique(train_labels_int)))
    logger.info(f"Computing cross-validated pred_probs ({n_splits}-fold) …")

    clf = LogisticRegression(max_iter=2000, C=1.0, class_weight="balanced", random_state=seed)
    train_pp = cross_val_predict(
        clf, emb["train"], train_labels_int, cv=n_splits, method="predict_proba",
    )

    clf.fit(emb["train"], train_labels_int)

    pred_probs: dict[str, np.ndarray] = {"train": train_pp}
    for name in ("val", "test"):
        pred_probs[name] = clf.predict_proba(emb[name])
    return pred_probs


def _audit_split(
    records: list[dict],
    embeddings: np.ndarray,
    pred_probs: np.ndarray,
    split_name: str,
    output_dir: Path,
) -> dict:
    """Run Datalab audit on a single split, persist and return the report.

    Args:
        records: JSONL records for this split.
        embeddings: Embedding array for this split.
        pred_probs: Prediction probabilities for this split.
        split_name: Split identifier (e.g. ``"train"``).
        output_dir: Directory where the report JSON is saved.

    Returns:
        The report dict produced for this split.
    """
    labels = [r["label"] for r in records]
    logger.info(f"Running Datalab audit on {split_name} ({len(records)} samples) …")
    datalab = run_datalab_audit(labels=labels, features=embeddings, pred_probs=pred_probs)
    report = generate_report(datalab, split_name)
    _write_report(report, output_dir, split_name)
    return report


def main(
    aot_root: str,
    input_dir: str,
    output_dir: str,
    dataset_name: str | None = None,
    dinov2_model: str = "vit_small_patch14_dinov2.lvd142m",
    dinov2_batch: int = 64,
    cv_folds: int = 5,
    seed: int = 0,
) -> None:
    """Audit the background-classification dataset using Cleanlab Datalab.

    Orchestrates the full audit pipeline: load splits, compute
    embeddings, derive prediction probabilities, audit each split with
    Datalab, populate FiftyOne with the audit signals and run
    ``fiftyone.brain`` uniqueness/mistakenness/hardness, and write outputs
    unchanged (no automatic removal).

    All defaults are loaded from dvc_config.yaml. Override any by passing explicitly.

    Args:
        aot_root: Root path to the AOT dataset on NAS.
        input_dir: Directory with ``train.jsonl``, ``val.jsonl``,
            ``test.jsonl`` from stage 01.
        output_dir: Output directory for JSONL files (unchanged),
            reports, cached embeddings, and the audit snapshot.
        dataset_name: Name of the FiftyOne dataset to (re)create.
        dinov2_model: ``timm`` model identifier for DINOv2 backbone.
        dinov2_batch: Batch size for DINOv2 inference.
        cv_folds: Number of cross-validation folds for out-of-sample
            ``pred_probs`` on the training set.
        seed: Random seed for reproducibility.
    """
    dataset_name = dataset_name or load_fiftyone_dataset_name()

    aot_root_p = Path(aot_root)
    input_dir_p = Path(input_dir)
    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)

    device = "cuda" if torch.cuda.is_available() else "cpu"
    np.random.seed(seed)

    splits = _load_splits(input_dir_p)
    emb = _compute_all_embeddings(splits, aot_root_p, dinov2_model, dinov2_batch, device)
    pred_probs = _compute_pred_probs(emb, splits["train"], cv_folds, seed)

    _save_embeddings(emb, output_dir_p)

    # Audit all splits (no filtering — all records pass through unchanged)
    reports: dict[str, dict] = {}
    for name in SPLIT_NAMES:
        reports[name] = _audit_split(
            splits[name], emb[name], pred_probs[name], name, output_dir_p,
        )
        write_jsonl(output_dir_p / f"{name}.jsonl", splits[name])
        logger.info(f"Wrote {output_dir_p / f'{name}.jsonl'} ({len(splits[name])} records)")

    # Populate FiftyOne with audit signals + fiftyone.brain analyses and
    # export a DVC-tracked snapshot for traceability before manual review.
    build_and_audit(
        dataset_name=dataset_name,
        splits=splits,
        embeddings=emb,
        pred_probs=pred_probs,
        reports=reports,
        classes=list(CLASSES),
        aot_root=aot_root_p,
        snapshot_path=output_dir_p / "audit_snapshot.jsonl",
        seed=seed,
    )

    logger.success("Dataset audit complete.")


if __name__ == "__main__":
    fire.Fire(main)
