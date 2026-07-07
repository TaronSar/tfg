"""Build the crops FiftyOne dataset for detection + ID/OOD visualisation.

Stage 11 of the OOD pipeline.  Materialises a persistent FiftyOne dataset of
detection *crops* (clean crops and corrupted crops) each carrying:

* YOLOX ground-truth and predicted bounding boxes (crop-local) from stage 07,
* the corruption type / severity (``None`` / ``0`` for clean crops),
* the background-classification label inherited from the parent full frame, and
* the energy OOD score and ID-vs-OOD verdict inherited from the parent full
  frame (matched on source frame + corruption variant).

A DVC-tracked JSONL snapshot and a stamp file are written to *output_dir*.
"""
from __future__ import annotations

from pathlib import Path

import fiftyone as fo
import fire
from loguru import logger

from src.ood.common.fiftyone_utils import build_ood_fiftyone_dataset, to_fo_detections
from src.ood.common.io import read_jsonl


def _load_background_by_frame(curated_dir: Path, splits: tuple[str, ...]) -> dict[str, str]:
    """Map each source frame path to its background label.

    Args:
        curated_dir: Directory of curated background JSONLs (``<split>.jsonl``).
        splits: Splits to include.

    Returns:
        Mapping ``{source_frame_path: background_label}``.
    """
    bg: dict[str, str] = {}
    for split in splits:
        path = curated_dir / f"{split}.jsonl"
        if not path.exists():
            continue
        for rec in read_jsonl(path):
            bg[rec["path"]] = rec["label"]
    return bg


def build_fiftyone_crops(
    detection_crops_jsonl: str,
    curated_dir: str,
    ood_samples_jsonl: str,
    output_dir: str,
    dataset_name: str,
    splits: str = "train,val,test",
) -> None:
    """Build the crops FiftyOne dataset plus DVC snapshot.

    Args:
        detection_crops_jsonl: Per-crop GT/prediction export from stage 07
            (``detection_samples.crops.jsonl``).
        curated_dir: Directory of curated background JSONLs (stage 04), used to
            inherit the parent-frame background label.
        ood_samples_jsonl: Per-sample OOD export from stage 09
            (``ood_per_sample.jsonl``), used to inherit the parent-frame
            ID/OOD verdict and score.
        output_dir: Directory for snapshot/stamp artifacts.
        dataset_name: FiftyOne persistent dataset name to (re)create.
        splits: Comma-separated splits whose background labels are loaded.
    """
    crops_path = Path(detection_crops_jsonl)
    curated_dir_p = Path(curated_dir)
    ood_path = Path(ood_samples_jsonl)
    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)
    if isinstance(splits, str):
        split_tuple = tuple(s.strip() for s in splits.split(",") if s.strip())
    else:
        split_tuple = tuple(splits)

    crop_rows = read_jsonl(crops_path) if crops_path.exists() else []
    logger.info(f"Loaded {len(crop_rows):,} crop rows from {crops_path}")

    bg_by_frame = _load_background_by_frame(curated_dir_p, split_tuple)
    logger.info(f"Loaded {len(bg_by_frame):,} background labels")
    for row in crop_rows:
        source_frame = row.get("source_frame")
        if source_frame is not None:
            row["background_label_gt"] = bg_by_frame.get(str(source_frame))
        row.setdefault("source_variant", row.get("variant", "clean"))

    # Parent-frame ID/OOD verdict keyed by (source_frame, variant).
    ood_rows = read_jsonl(ood_path) if ood_path.exists() else []
    ood_by_frame_variant: dict[tuple[str, str], dict] = {}
    for r in ood_rows:
        source_frame = r.get("source_frame")
        variant = r.get("variant")
        if source_frame is not None and variant is not None:
            ood_by_frame_variant[(str(source_frame), str(variant))] = r
    logger.info(f"Loaded {len(ood_by_frame_variant):,} parent-frame OOD verdicts")

    def _get_ood(row: dict, _fp: str) -> dict | None:
        source_frame = row.get("source_frame")
        variant = row.get("source_variant", "clean")
        if source_frame is None:
            return None
        return ood_by_frame_variant.get((str(source_frame), str(variant)))

    def _enrich(sample: fo.Sample, row: dict) -> None:
        w = int(row.get("image_width", 1))
        h = int(row.get("image_height", 1))
        sample["ground_truth"] = to_fo_detections(row.get("detection_gt", []), w, h, False)
        sample["predictions"] = to_fo_detections(row.get("detection_pred", []), w, h, True)

    def _extra_snapshot(row: dict) -> dict:
        return {
            "detection_gt_count": len(row.get("detection_gt", [])),
            "detection_pred_count": len(row.get("detection_pred", [])),
        }

    def _extra_stats(snapshot_rows: list[dict]) -> dict:
        return {"num_with_predictions": sum(1 for r in snapshot_rows if r["detection_pred_count"] > 0)}

    build_ood_fiftyone_dataset(
        rows=crop_rows,
        get_ood=_get_ood,
        enrich_sample=_enrich,
        extra_snapshot_fields=_extra_snapshot,
        extra_stats=_extra_stats,
        index_fields=(
            "source_variant",
            "group_id",
            "background_label_gt",
            "background_label_pred",
            "corruption_type",
            "corruption_severity",
            "ood_label",
            "predictions.detections.confidence",
        ),
        dataset_name=dataset_name,
        dataset_description="OOD crops visual dataset",
        output_dir=output_dir_p,
        stamp_name="11_build_fiftyone_crops.stamp",
        snapshot_filename="fiftyone_crops_snapshot.jsonl",
        stats_filename="fiftyone_crops_stats.jsonl",
    )


if __name__ == "__main__":
    fire.Fire(build_fiftyone_crops)
