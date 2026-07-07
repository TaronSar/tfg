"""Helpers for stage 03b: export the CVAT relabel queue as a JSONL artifact."""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.ood.common.io import write_jsonl
from src.ood.curation._typing import FiftyOneDatasetLike


def build_queue_rows(dataset: FiftyOneDatasetLike, anno_key: str) -> list[dict]:
    """Build queue rows from samples tagged with relabel.

    Stores minimal metadata needed to match queue entries back to dataset samples.
    Detailed traceability (split, label, tags, etc.) is captured in the curation
    snapshot after annotation completes.

    Args:
        dataset: Loaded FiftyOne dataset or pre-filtered view.
        anno_key: Annotation round key for CVAT.

    Returns:
        JSON-serializable rows for the queue artifact with essential fields only.
    """
    rows: list[dict] = []
    for sample in dataset:
        rows.append(
            {
                "sample_id": str(sample.id),
                "filename": Path(sample.filepath).name,
                "anno_key": anno_key,
            }
        )
    return rows


def validate_queue_nonempty(rows: list[dict], allow_empty: bool = False) -> bool:
    """Validate queue rows and optionally allow empty queue as a no-op.

    Args:
        rows: Queue rows built from current FiftyOne tags.
        allow_empty: When ``True``, an empty queue is treated as a no-op.

    Returns:
        ``True`` when the queue has rows, ``False`` when empty and ``allow_empty`` is enabled.

    Raises:
        ValueError: If the queue is empty and ``allow_empty`` is ``False``.
    """
    if rows:
        return True

    if allow_empty:
        logger.warning(
            "No samples tagged 'relabel' to export. "
            "Continuing with empty queue artifact (no-op)."
        )
        return False

    raise ValueError("No samples tagged 'relabel' to export. Nothing to send to CVAT.")


def write_queue_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(path, rows)
    logger.success(f"Wrote CVAT queue snapshot -> {path} ({len(rows)} rows)")

