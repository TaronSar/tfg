"""Populate FiftyOne with audit signals and run ``fiftyone.brain`` analyses.

This module bridges the automated audit (Cleanlab/Datalab + embeddings)
and the FiftyOne dataset used for human-in-the-loop curation. It builds a
persistent FiftyOne dataset with ground-truth labels, predicted classifications,
per-issue Cleanlab flags, and runs the three ``fiftyone.brain`` analyses
(uniqueness, mistakenness, hardness) plus UMAP visualization over embeddings.

Finally it exports an ``audit_snapshot.jsonl`` file so the audit signals
living in MongoDB are captured as a DVC-tracked, human-readable artifact.

Requires ``fiftyone`` and ``fiftyone-brain`` packages plus a running
FiftyOne MongoDB backend.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from loguru import logger

from src.ood.common.constants import SPLIT_NAMES
from src.ood.common.io import write_jsonl
from src.ood.common.path_utils import image_path, parse_frame_path
PRED_FIELD = "predicted"
LABEL_FIELD = "label"
_LOGIT_EPS = 1e-9

# Cleanlab Datalab issue type for label errors.  The stored FiftyOne field is
# derived as  is_{CLEANLAB_LABEL_ISSUE_TYPE}_issue  = "is_label_issue".
CLEANLAB_LABEL_ISSUE_TYPE = "label"


def issue_field_name(issue_type: str) -> str:
    """Return the FiftyOne field name for a Cleanlab issue type.

    Centralises the naming convention ``is_{issue_type}_issue`` so that
    all modules that read or write issue flags use the same derivation and
    don't diverge when issue type names change.

    Args:
        issue_type: Cleanlab Datalab issue type (e.g. ``"label"``,
            ``"outlier"``, ``"near_duplicate"``).

    Returns:
        The FiftyOne field name (e.g. ``"is_label_issue"``).
    """
    return f"is_{issue_type}_issue"


def _flagged_index_from_report(report: dict | None) -> dict[str, set[int]]:
    """Build a per-issue-type index of flagged sample indices from a report.

    Args:
        report: Report dict produced by
            :func:`~src.ood.cleaning.auditor.generate_report`, or ``None``.

    Returns:
        Dict mapping issue type name to a set of flagged sample indices.
    """
    if not report or "per_issue_details" not in report:
        return {}
    return {
        issue_type: set(detail.get("flagged_indices", []))
        for issue_type, detail in report["per_issue_details"].items()
    }


def _resolve_filepath(rec: dict, aot_root: Path) -> str:
    """Resolve the absolute on-disk image path for a JSONL record."""
    part = rec.get("part") or parse_frame_path(rec["path"])[2]
    return str(image_path(rec["flight_id"], rec["img_name"], part, aot_root))


def _build_samples(
    records: list[dict],
    split_name: str,
    aot_root: Path,
    pred_probs: np.ndarray,
    classes: list[str],
    flagged: dict[str, set[int]],
) -> list:
    """Create FiftyOne ``Sample`` objects for one split.

    Each sample carries the ground-truth label, a ``predicted``
    classification (with ``logits`` derived from *pred_probs*), and the
    Cleanlab issue flags.

    Args:
        records: JSONL records for this split.
        split_name: Split identifier (``"train"``/``"val"``/``"test"``).
        aot_root: Root path to the AOT dataset on NAS.
        pred_probs: Prediction-probability matrix aligned to *records*.
        classes: Ordered class names matching the columns of *pred_probs*.
        flagged: Per-issue-type set of flagged sample indices.

    Returns:
        List of ``fiftyone.Sample`` objects.
    """
    import fiftyone as fo

    samples = []
    for i, rec in enumerate(records):
        sample = fo.Sample(filepath=_resolve_filepath(rec, aot_root))
        sample["split"] = split_name
        sample["flight_id"] = rec["flight_id"]
        sample[LABEL_FIELD] = fo.Classification(label=rec["label"])

        probs = pred_probs[i]
        top = int(np.argmax(probs))
        logits = np.log(probs + _LOGIT_EPS)
        sample[PRED_FIELD] = fo.Classification(
            label=classes[top],
            confidence=float(probs[top]),
            logits=logits.astype(float).tolist(),
        )

        for issue_type, idx_set in flagged.items():
            sample[issue_field_name(issue_type)] = i in idx_set

        samples.append(sample)
    return samples


def _ensure_dataset(dataset_name: str) -> object:
    """Create a fresh persistent FiftyOne dataset, replacing any existing one.

    Args:
        dataset_name: Name for the persistent FiftyOne dataset.

    Returns:
        A new ``fiftyone.Dataset`` instance with standard audit metadata.
    """
    import fiftyone as fo

    if fo.dataset_exists(dataset_name):
        logger.warning(f"Deleting existing dataset '{dataset_name}' …")
        fo.delete_dataset(dataset_name)

    dataset = fo.Dataset(dataset_name, persistent=True)
    dataset.info["description"] = (
        "OOD background-classification audit: Cleanlab Datalab issues + "
        "fiftyone.brain uniqueness/mistakenness/hardness over embeddings"
    )
    return dataset


def _run_brain(dataset, embeddings: np.ndarray, seed: int) -> None:
    """Run uniqueness, mistakenness, hardness, and a UMAP visualization.

    Args:
        dataset: FiftyOne dataset with all splits in insertion order.
        embeddings: embedding matrix aligned to dataset sample order.
        seed: Random seed for the UMAP visualization.
    """
    import fiftyone.brain as fob

    logger.info("fiftyone.brain: computing uniqueness …")
    fob.compute_uniqueness(dataset, embeddings=embeddings)

    logger.info("fiftyone.brain: computing mistakenness …")
    fob.compute_mistakenness(dataset, PRED_FIELD, label_field=LABEL_FIELD)

    logger.info("fiftyone.brain: computing hardness …")
    fob.compute_hardness(dataset, PRED_FIELD)

    logger.info("fiftyone.brain: computing UMAP visualization …")
    fob.compute_visualization(
        dataset,
        embeddings=embeddings,
        num_dims=2,
        method="umap",
        brain_key="dinov2_viz",
        verbose=True,
        seed=seed,
    )


def _export_snapshot(dataset, snapshot_path: Path) -> None:
    """Export per-sample audit signals to a JSONL snapshot for DVC tracking.

    Args:
        dataset: FiftyOne dataset after brain analyses have run.
        snapshot_path: Destination ``.jsonl`` path.
    """
    issue_fields = [f for f in dataset.get_field_schema().keys() if f.endswith("_issue")]
    rows: list[dict] = []
    for sample in dataset:
        row = {
            "filename": Path(sample.filepath).name,
            "split": sample["split"],
            "flight_id": sample["flight_id"],
            "label": sample[LABEL_FIELD].label,
            "predicted": sample[PRED_FIELD].label,
            "pred_confidence": sample[PRED_FIELD].confidence,
            "uniqueness": sample.get_field("uniqueness"),
            "mistakenness": sample.get_field("mistakenness"),
            "hardness": sample.get_field("hardness"),
            "tags": list(sample.tags),
        }
        for field in issue_fields:
            row[field] = bool(sample[field]) if sample[field] is not None else False
        rows.append(row)

    write_jsonl(snapshot_path, rows)
    logger.success(f"Wrote audit snapshot → {snapshot_path} ({len(rows)} samples)")


def build_and_audit(
    dataset_name: str,
    splits: dict[str, list[dict]],
    embeddings: dict[str, np.ndarray],
    pred_probs: dict[str, np.ndarray],
    reports: dict[str, dict],
    classes: list[str],
    aot_root: Path,
    snapshot_path: Path,
    seed: int = 42,
) -> None:
    """Build the FiftyOne audit dataset and run all brain analyses.

    Args:
        dataset_name: Name of the persistent FiftyOne dataset to (re)create.
        splits: Dict mapping split name to its JSONL records.
        embeddings: Dict mapping split name to its embedding array.
        pred_probs: Dict mapping split name to its prediction-probability
            matrix.
        reports: Dict mapping split name to its Cleanlab report dict.
        classes: Ordered class names matching ``pred_probs`` columns.
        aot_root: Root path to the AOT dataset on NAS.
        snapshot_path: Destination for the exported ``audit_snapshot.jsonl``.
        seed: Random seed for the UMAP visualization.
    """
    dataset = _ensure_dataset(dataset_name)

    emb_arrays: list[np.ndarray] = []
    for name in SPLIT_NAMES:
        records = splits.get(name, [])
        if not records:
            continue
        flagged = _flagged_index_from_report(reports.get(name))
        samples = _build_samples(
            records, name, aot_root, pred_probs[name], classes, flagged,
        )
        dataset.add_samples(samples)
        emb_arrays.append(embeddings[name])
        logger.info(f"Added {len(samples)} {name} samples to FiftyOne")

    if not emb_arrays:
        logger.warning("No samples added to FiftyOne — skipping brain analyses.")
        return

    all_embeddings = np.concatenate(emb_arrays, axis=0)
    _run_brain(dataset, all_embeddings, seed)
    dataset.save()

    logger.info("Computing sidebar groups for numeric fields (mistakenness, hardness, uniqueness, etc.) …")
    dataset.create_index("hardness")
    dataset.create_index("mistakenness")
    dataset.create_index("uniqueness")

    _export_snapshot(dataset, snapshot_path)
    logger.success(
        f"FiftyOne dataset '{dataset_name}' audited with "
        f"{len(dataset)} samples (uniqueness, mistakenness, hardness, UMAP)."
    )
