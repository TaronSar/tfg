"""Curation snapshot: export the live FiftyOne/Mongo curation state to a JSONL file.

This module exports per-sample curation decisions (exclusions, relabels, brain scores)
so the exact human-curation state that produced the curated dataset is versioned
by DVC for data governance and traceability.
"""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.ood.common.fiftyone_utils import load_fiftyone_dataset
from src.ood.common.io import write_jsonl
from src.ood.curation.cvat_sync import EXCLUDE_TAG, RELABEL_TAG_PREFIX


def export_curation_snapshot(dataset_name: str, snapshot_path: Path) -> list[dict]:
    """Export the live FiftyOne/Mongo curation state to a JSONL snapshot.

    Every sample's tags, derived relabel/exclude decision, and brain scores are
    captured so the exact human-curation state that produced the curated dataset
    is versioned by DVC.

    Args:
        dataset_name: Name of the persistent FiftyOne dataset.
        snapshot_path: Destination ``.jsonl`` path.

    Returns:
        The list of per-sample snapshot rows (also written to disk).

    Raises:
        ValueError: If the dataset does not exist.
    """
    dataset = load_fiftyone_dataset(dataset_name)

    rows: list[dict] = []
    for sample in dataset:
        tags = list(sample.tags)
        exclude = EXCLUDE_TAG in tags
        relabel_tags = [
            t[len(RELABEL_TAG_PREFIX):] for t in tags if t.startswith(RELABEL_TAG_PREFIX)
        ]
        if len(relabel_tags) > 1:
            logger.warning(
                f"Sample {Path(sample.filepath).name!r} has multiple relabel tags "
                f"{relabel_tags!r} — using the first in sorted order: {sorted(relabel_tags)[0]!r}"
            )
        relabel = sorted(relabel_tags)[0] if relabel_tags else None
        rows.append(
            {
                "filename": Path(sample.filepath).name,
                "split": sample["split"],
                "label": sample["label"].label,
                "tags": tags,
                "exclude": exclude,
                "relabel": relabel,
                "mistakenness": sample.get_field("mistakenness"),
                "hardness": sample.get_field("hardness"),
                "uniqueness": sample.get_field("uniqueness"),
            }
        )

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(snapshot_path, rows)
    logger.success(f"Wrote curation snapshot → {snapshot_path} ({len(rows)} samples)")
    return rows
