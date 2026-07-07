"""Helpers for stage 03c: pull CVAT annotations and persist resolved decisions."""
from __future__ import annotations

from pathlib import Path

from loguru import logger

from src.ood.common.io import utc_now_iso, write_jsonl
from src.ood.curation._typing import FiftyOneDatasetLike
from src.ood.curation.cvat_sync import EXCLUDE_TAG, RELABEL_TAG_PREFIX


def assert_annotation_run_complete(
    dataset: FiftyOneDatasetLike, anno_key: str, skip_check: bool = False
) -> None:
    """Verify that an annotation run exists and prompt for task completion status.

    FiftyOne does NOT automatically update task status when a CVAT task completes.
    The operator must confirm the task is done before proceeding to pull annotations.

    In non-TTY (CI) environments the interactive prompt is skipped and a warning
    is logged instead. Pass ``skip_check=True`` to suppress both.

    Args:
        dataset: FiftyOne dataset containing annotation runs.
        anno_key: Annotation key identifying the workflow run.
        skip_check: If True, skip all prompts and validation.

    Raises:
        ValueError: If the annotation run does not exist or if the operator
            declines to proceed in TTY mode.
    """
    import sys

    runs = set(dataset.list_annotation_runs())
    if anno_key not in runs:
        msg = (
            f"Annotation run '{anno_key}' not found. "
            "Ensure the annotation queue has been exported first."
        )
        logger.error(msg)
        raise ValueError(msg)

    if skip_check:
        return

    if sys.stdin.isatty():
        answer = input(
            f"\n\u26a0  Have you completed ALL jobs for annotation run '{anno_key}' in CVAT?"
            " [yes/no]: "
        ).strip().lower()
        if answer not in {"yes", "y"}:
            msg = (
                "Aborting annotation pull. Complete the annotation task first, "
                "then rerun this workflow."
            )
            logger.error(msg)
            raise ValueError(msg)
    else:
        logger.warning(
            f"Non-TTY environment: skipping CVAT completion prompt for '{anno_key}'. "
            "Assuming task is complete. Pass --skip_status_check to silence this."
        )


def _resolved_action_from_tags(tags: list[str]) -> tuple[str | None, str | None]:
    if EXCLUDE_TAG in tags:
        return "exclude", None
    relabel_tags = [t for t in tags if t.startswith(RELABEL_TAG_PREFIX)]
    if relabel_tags:
        relabel_tags.sort()
        cls = relabel_tags[0][len(RELABEL_TAG_PREFIX):]
        return "relabel", cls
    return None, None


def build_annotations_rows(
    dataset: FiftyOneDatasetLike,
    queue_rows: list[dict],
    anno_key: str,
) -> list[dict]:
    """Build annotation workflow results from resolved decisions.

    Reconciles samples from the export queue with their annotation backend
    results, extracting the resolved action (exclude/relabel) and any
    reassigned class label.

    Args:
        dataset: FiftyOne dataset containing annotated samples.
        queue_rows: Original queue export records to match against.
        anno_key: Annotation workflow key for metadata tracking.

    Returns:
        List of dicts with keys: sample_id, filename, anno_key,
        resolved_action, resolved_relabel, tags, pulled_at.
    """
    by_sample_id: dict[str, object] = {}
    by_filename: dict[str, object] = {}

    for sample in dataset:
        sample_id = str(sample.id)
        filename = Path(sample.filepath).name
        by_sample_id[sample_id] = sample
        by_filename[filename] = sample

    rows: list[dict] = []
    for q in queue_rows:
        sample = by_sample_id.get(str(q.get("sample_id")))
        if sample is None:
            sample = by_filename.get(str(q.get("filename")))
        if sample is None:
            continue

        tags = list(sample.tags)
        action, relabel = _resolved_action_from_tags(tags)
        rows.append(
            {
                "sample_id": str(sample.id),
                "filename": Path(sample.filepath).name,
                "anno_key": anno_key,
                "resolved_action": action,
                "resolved_relabel": relabel,
                "tags": tags,
                "pulled_at": utc_now_iso(),
            }
        )

    return rows


def write_annotations_jsonl(path: Path, rows: list[dict]) -> None:
    """Persist annotation workflow results to a JSONL artifact.

    Args:
        path: Output file path for the JSONL artifact.
        rows: Annotation decision records to persist.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    write_jsonl(path, rows)
    logger.success(f"Wrote annotation results -> {path} ({len(rows)} rows)")
