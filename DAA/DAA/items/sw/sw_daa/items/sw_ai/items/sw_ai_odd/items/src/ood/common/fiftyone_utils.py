"""Common FiftyOne utilities shared across curation scripts."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from loguru import logger

from src.ood.common.io import write_jsonl


def load_fiftyone_dataset(dataset_name: str):
    """Load a FiftyOne dataset by name.

    Args:
        dataset_name: Name of the persistent FiftyOne dataset.

    Returns:
        A ``fiftyone.Dataset`` instance.

    Raises:
        ValueError: If the dataset does not exist.
    """
    import fiftyone as fo

    if not fo.dataset_exists(dataset_name):
        msg = f"Dataset '{dataset_name}' not found. Run 02_audit_dataset first."
        logger.error(msg)
        raise ValueError(msg)
    return fo.load_dataset(dataset_name)


def to_rel_box(bbox_abs: list[float], width: int, height: int) -> list[float] | None:
    """Convert a COCO absolute ``[x, y, w, h]`` box to FiftyOne relative coords.

    Clips to the unit square and drops degenerate (zero-area) boxes.

    Args:
        bbox_abs: Absolute COCO box ``[x, y, w, h]`` in pixels.
        width: Image width in pixels.
        height: Image height in pixels.

    Returns:
        ``[x, y, w, h]`` in normalised ``[0, 1]`` coordinates, or ``None`` if
        the image dimensions or resulting box are invalid.
    """
    if width <= 0 or height <= 0:
        return None

    x, y, w, h = bbox_abs
    x1 = max(0.0, min(1.0, float(x) / float(width)))
    y1 = max(0.0, min(1.0, float(y) / float(height)))
    x2 = max(0.0, min(1.0, float(x + w) / float(width)))
    y2 = max(0.0, min(1.0, float(y + h) / float(height)))

    w_rel = x2 - x1
    h_rel = y2 - y1
    if w_rel <= 0.0 or h_rel <= 0.0:
        return None
    return [x1, y1, w_rel, h_rel]


def to_fo_detections(entries: list[dict], width: int, height: int, with_confidence: bool):
    """Build a ``fiftyone.Detections`` object from serialised detection rows.

    Args:
        entries: List of ``{label, bbox_abs, [confidence]}`` dicts.
        width: Image width in pixels.
        height: Image height in pixels.
        with_confidence: Whether to attach a ``confidence`` field to each box.

    Returns:
        A ``fiftyone.Detections`` instance (possibly empty).
    """
    import fiftyone as fo

    dets = []
    for item in entries:
        rel_box = to_rel_box(item["bbox_abs"], width, height)
        if rel_box is None:
            continue
        det = fo.Detection(label=item["label"], bounding_box=rel_box)
        if with_confidence:
            det.confidence = float(item.get("confidence", 0.0))
        dets.append(det)
    return fo.Detections(detections=dets)


def resolve_image_path(raw_filepath: str | None) -> str | None:
    """Resolve and validate an image filepath for a FiftyOne sample.

    Uses ``Path.absolute()`` (NOT ``Path.resolve()``) so DVC symlinks keep
    their ``.png`` extension; ``resolve()`` would follow the symlink to a
    hash-named cache file with no extension, causing FiftyOne to report a media
    type of ``unknown``.

    Args:
        raw_filepath: Candidate filepath (may be relative or ``None``).

    Returns:
        The validated absolute filepath string, or ``None`` if the path is
        missing, not a file, or not recognised as an image.
    """
    import fiftyone.core.media as fom

    if not raw_filepath:
        return None
    input_path = Path(raw_filepath).expanduser()
    file_path_obj = (
        input_path.absolute() if input_path.is_absolute() else (Path.cwd() / input_path).absolute()
    )
    if not file_path_obj.is_file():
        logger.warning(f"Skipping sample with missing/non-file filepath: {file_path_obj}")
        return None
    if fom.get_media_type(str(file_path_obj)) != "image":
        logger.warning(f"Skipping sample with unrecognised media type: {file_path_obj}")
        return None
    return str(file_path_obj)


def build_ood_fiftyone_dataset(
    rows: list[dict],
    get_ood: Callable[[dict, str], dict | None],
    enrich_sample: Callable[[Any, dict], None],
    extra_snapshot_fields: Callable[[dict], dict],
    extra_stats: Callable[[list[dict]], dict],
    index_fields: Sequence[str],
    dataset_name: str,
    dataset_description: str,
    output_dir: Path,
    stamp_name: str,
    snapshot_filename: str,
    stats_filename: str,
) -> None:
    """Create/replace a persistent FiftyOne OOD dataset and write DVC artifacts.

    Shared core for all OOD FiftyOne dataset builders.  Handles dataset
    lifecycle (delete-then-create), the per-sample dedup loop, common sample
    field assignment, snapshot + stats JSONL writing, and the DVC stamp file.

    Each *row* in *rows* must contain (at minimum) the following normalised
    keys: ``filepath``, ``source_variant``, ``source_frame``,
    ``corruption_type``, ``corruption_severity``, ``background_label_gt``.

    Args:
        rows: Pre-loaded flat sample dicts (one per frame variant).
        get_ood: ``(row, resolved_filepath) -> ood_row | None``.  Returns the
            OOD-scoring result dict for the given row, or ``None`` if no match.
        enrich_sample: ``(sample, row) -> None``.  Called after common fields
            are set; should add dataset-specific ``fo.Sample`` fields in-place.
        extra_snapshot_fields: ``(row) -> dict`` of extra keys to merge into
            the common snapshot entry for each sample.
        extra_stats: ``(snapshot_rows) -> dict`` of extra keys to merge into the
            common stats dict.
        index_fields: FiftyOne fields to index on the created dataset.
        dataset_name: FiftyOne persistent dataset name to (re)create.
        dataset_description: Human-readable description stored in ``ds.info``.
        output_dir: Directory for snapshot/stamp artifacts (must already exist).
        stamp_name: Filename of the DVC stamp file (e.g. ``"10_foo.stamp"``).
        snapshot_filename: Filename for the JSONL snapshot artifact.
        stats_filename: Filename for the JSONL stats artifact.
    """
    import fiftyone as fo

    if fo.dataset_exists(dataset_name):
        logger.warning(f"Deleting existing dataset '{dataset_name}' …")
        fo.delete_dataset(dataset_name)
    ds = fo.Dataset(dataset_name, persistent=True)
    ds.info["description"] = dataset_description

    samples: list = []
    snapshot_rows: list[dict] = []
    seen: set[str] = set()
    skipped = 0

    for row in rows:
        fp = resolve_image_path(row.get("filepath"))
        if fp is None:
            skipped += 1
            continue
        if row.get("source_frame") is None:
            skipped += 1
            continue
        if fp in seen:
            continue
        seen.add(fp)

        ood = get_ood(row, fp)
        ood_score: float | None = None
        if ood is not None and ood.get("ood_score_energy") is not None:
            ood_score = float(ood["ood_score_energy"])

        sample = fo.Sample(filepath=fp)
        sample["source_variant"] = row.get("source_variant")
        sample["source_frame"] = row.get("source_frame")
        sample["group_id"] = row.get("source_frame")
        sample["corruption_type"] = row.get("corruption_type")
        sample["corruption_severity"] = int(row.get("corruption_severity") or 0)
        sample["background_label_gt"] = row.get("background_label_gt")
        sample["background_label_pred"] = None if ood is None else ood.get("background_label_pred")
        sample["ood_score_energy"] = ood_score
        sample["ood_label"] = None if ood is None else ood.get("ood_label_id_vs_ood")
        enrich_sample(sample, row)
        samples.append(sample)

        base_snapshot: dict = {
            "filepath": fp,
            "source_variant": sample["source_variant"],
            "source_frame": sample["source_frame"],
            "corruption_type": sample["corruption_type"],
            "corruption_severity": sample["corruption_severity"],
            "background_label_gt": sample["background_label_gt"],
            "background_label_pred": sample["background_label_pred"],
            "ood_score_energy": sample["ood_score_energy"],
            "ood_label": sample["ood_label"],
        }
        base_snapshot.update(extra_snapshot_fields(row))
        snapshot_rows.append(base_snapshot)

    if samples:
        ds.add_samples(samples)
        for field in index_fields:
            ds.create_index(field)

    snapshot_path = output_dir / snapshot_filename
    write_jsonl(snapshot_path, snapshot_rows)

    stats: dict = {
        "dataset_name": dataset_name,
        "num_samples": len(samples),
        "num_clean": sum(1 for r in snapshot_rows if r.get("source_variant") == "clean"),
        "num_corrupted": sum(1 for r in snapshot_rows if r.get("source_variant") != "clean"),
        "skipped_missing_filepaths": skipped,
    }
    stats.update(extra_stats(snapshot_rows))
    write_jsonl(output_dir / stats_filename, [stats])
    (output_dir / stamp_name).write_text("ok\n", encoding="utf-8")

    logger.success(
        f"FiftyOne dataset '{dataset_name}' created with {len(samples)} samples. "
        f"Snapshot: {snapshot_path}"
    )
