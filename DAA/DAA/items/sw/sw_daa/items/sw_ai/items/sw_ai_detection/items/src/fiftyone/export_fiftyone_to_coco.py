from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

import fiftyone as fo
from src.fiftyone._utils import (
    apply_label_filters,
    apply_sample_tag_filters,
    configure_fiftyone,
    parse_label_filters,
)
from src.preprocessing.utils.coco_json_io import (
    build_categories,
    build_coco_skeleton,
    get_or_add_category,
    save_coco_json,
)

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)

MISSING = -1

# FiftyOne Detection fields handled explicitly — everything else is forwarded
# as a custom annotation attribute in the COCO output.
_STANDARD_DET_FIELDS = {
    "id",
    "label",
    "bounding_box",
    "confidence",
    "index",
    "tags",
    "attributes",
    "bbox_width",
    "bbox_height",
    "bbox_area",
}


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the COCO export script.

    Returns:
        Parsed arguments namespace with dataset-name, output-path,
        include-tags, exclude-tags, images-dir, and version.
    """
    parser = argparse.ArgumentParser(description="Export a FiftyOne dataset to extended COCO JSON")
    parser.add_argument("--dataset-name", required=True, help="Name of the FiftyOne dataset")
    parser.add_argument(
        "--output-path",
        required=True,
        help="Path for the output COCO JSON file",
    )
    parser.add_argument(
        "--images-dir",
        required=False,
        help=(
            "If provided, image file_name in the output will be relative to "
            "this directory. Otherwise absolute paths are used."
        ),
    )
    parser.add_argument(
        "--version",
        required=True,
        help=("Filter samples by version field. Also used as the COCO info.version string."),
    )
    parser.add_argument(
        "--include-labels",
        nargs="+",
        required=False,
        help="Include only samples that have any of these labels "
        "(select & label images in the FiftyOne App)",
    )
    parser.add_argument(
        "--exclude-labels",
        nargs="+",
        required=False,
        help="Exclude samples that have any of these labels "
        "(e.g. 'excluded noisy'). Applied after --include-labels filtering.",
    )
    parser.add_argument(
        "--exclude-tags",
        nargs="+",
        required=False,
        help="Exclude samples that carry any of these sample-level tags "
        "(e.g. 'remove_flock'). Applied after label filtering.",
    )
    parser.add_argument(
        "--include-tags",
        nargs="+",
        required=False,
        help="Include only samples that carry any of these sample-level tags "
        "(e.g. 'keep_flock'). Applied after --exclude-tags filtering.",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        required=True,
        help="Ordered class names for category IDs",
    )
    parser.add_argument(
        "--label-field",
        default="ground_truth",
        help="FiftyOne label field to export as annotations (default: ground_truth)",
    )
    return parser.parse_args()


def _resolve_file_name(filepath: str, images_dir: str | None) -> str:
    """Compute file_name relative to *images_dir*, or absolute if not under it."""
    if images_dir is not None:
        try:
            return str(Path(filepath).relative_to(images_dir))
        except ValueError:
            return filepath
    return filepath


def _bbox_to_absolute(rel_bbox: list[float], img_w: int, img_h: int) -> list[float]:
    """Convert FiftyOne relative bbox ``[x, y, w, h]`` to absolute pixel coords."""
    rx, ry, rw, rh = rel_bbox
    return [rx * img_w, ry * img_h, rw * img_w, rh * img_h]


def _build_video_entry(video_id: int, sample: Any) -> dict[str, Any]:
    """Build a COCO video dict from the first sample of that video."""
    meta = sample.metadata
    return {
        "id": video_id,
        "file_name": (sample.get_field("video_path") if sample.has_field("video_path") else None),
        "width": meta.width if meta else None,
        "height": meta.height if meta else None,
        "fps": sample.get_field("video_fps") if sample.has_field("video_fps") else None,
        "num_frames": (
            sample.get_field("video_num_frames") if sample.has_field("video_num_frames") else None
        ),
    }


def _get_sample_field(sample: Any, field: str) -> int:
    """Read an integer sample field, returning ``MISSING`` when absent or None."""
    if sample.has_field(field):
        val = sample.get_field(field)
        if val is not None:
            return int(val)
    return MISSING


def export_fiftyone_to_extended_coco(
    dataset: fo.Dataset,
    output_json: str,
    classes: list[str],
    images_dir: str | None = None,
    version: str = "1.0",
    include_labels: dict[str, list[str]] | None = None,
    exclude_labels: dict[str, list[str]] | None = None,
    exclude_tags: list[str] | None = None,
    include_tags: list[str] | None = None,
    label_field: str = "ground_truth",
) -> None:
    """Export a FiftyOne dataset (or view) to an extended COCO JSON file.

    The output matches the schema produced by
    ``airborne_tracking_dataset_to_coco.py``, including top-level ``videos``
    and ``tracks`` lists.  All IDs (image, video, track, annotation) are
    regenerated as sequential integers so the output is always a valid
    standalone COCO file, even when the source dataset was assembled from
    multiple COCO files with overlapping IDs.

    Args:
        dataset: FiftyOne ``Dataset`` or ``DatasetView`` to export.
        output_json: Destination path for the COCO JSON file.  Parent
            directories are created automatically.
        classes: Ordered class names for category IDs.
        images_dir: When provided, ``file_name`` in each image entry will be
            stored relative to this directory.  Falls back to the absolute
            filepath when the sample path is not under *images_dir*.
        version: Version string written into ``info.version``.
        include_labels: If given, only samples carrying **any** of these labels
            are exported.
        exclude_labels: If given, samples carrying **any** of these labels are
            excluded.  Applied after *include_labels* filtering.
        exclude_tags: If given, samples carrying **any** of these sample-level
            tags are excluded.  Applied after label filtering.
        include_tags: If given, only samples carrying **any** of these sample-level
            tags are exported. Applied after *exclude_tags* filtering.
    """
    view = apply_label_filters(dataset, include_labels, exclude_labels)
    view = apply_sample_tag_filters(view, exclude_tags, include_tags)

    logger.info(f"Exporting {len(view)} samples")

    if hasattr(view, "count") and view.count() == 0:
        logger.error("No samples remaining after label filtering")
        return

    categories, name_to_id = build_categories(classes)
    coco = build_coco_skeleton(version=version, categories=categories)

    # Remap IDs to guarantee uniqueness — source files may have overlapping IDs.
    video_id_map: dict[int, int] = {}
    track_key_map: dict[tuple[int, int], int] = {}  # (orig_video_id, orig_track_id) → new
    next_video_id = 1
    next_track_id = 1
    next_image_id = 1
    annotation_id = 1

    for sample in tqdm(view.iter_samples(), desc="Building COCO JSON"):
        image_id = next_image_id
        next_image_id += 1

        # ---- video (remap to sequential IDs) ----
        orig_video_id = _get_sample_field(sample, "video_id")
        frame_id = _get_sample_field(sample, "frame_id")

        new_video_id: int | None = None
        if orig_video_id != MISSING:
            if orig_video_id not in video_id_map:
                video_id_map[orig_video_id] = next_video_id
                coco["videos"].append(_build_video_entry(next_video_id, sample))
                next_video_id += 1
            new_video_id = video_id_map[orig_video_id]

        # ---- image ----
        meta = sample.metadata
        img_w = meta.width if meta else None
        img_h = meta.height if meta else None

        coco["images"].append(
            {
                "id": image_id,
                "width": img_w,
                "height": img_h,
                "file_name": _resolve_file_name(sample.filepath, images_dir),
                "video_id": new_video_id,
                "frame_id": frame_id if frame_id != MISSING else None,
            }
        )

        # ---- annotations ----
        if not sample.has_field(label_field) or sample.get_field(label_field) is None:
            continue

        for det in sample.get_field(label_field).detections:
            category_id = get_or_add_category(det.label, name_to_id, coco["categories"])

            bbox = _bbox_to_absolute(det.bounding_box, img_w or 1, img_h or 1)

            # Track handling — remap (video_id, track_index) to new sequential ID
            orig_track_id = getattr(det, "index", MISSING)
            new_track_id: int | None = None
            if orig_track_id != MISSING:
                track_key = (orig_video_id, orig_track_id)
                if track_key not in track_key_map:
                    track_key_map[track_key] = next_track_id
                    coco["tracks"].append(
                        {
                            "id": next_track_id,
                            "category_id": category_id,
                            "video_id": new_video_id,
                        }
                    )
                    next_track_id += 1
                new_track_id = track_key_map[track_key]

            ann_entry: dict[str, Any] = {
                "id": annotation_id,
                "image_id": image_id,
                "category_id": category_id,
                "bbox": bbox,
                "area": bbox[2] * bbox[3],
                "iscrowd": 0,
                "segmentation": [],
                "track_id": new_track_id,
            }

            for attr_name in det.field_names:
                if attr_name in _STANDARD_DET_FIELDS:
                    continue
                val = det[attr_name]
                if val is not None:
                    ann_entry[attr_name] = val

            coco["annotations"].append(ann_entry)
            annotation_id += 1

    save_coco_json(coco, output_json, indent=2)

    logger.info(
        f"Exported {len(coco['images'])} images, "
        f"{len(coco['annotations'])} annotations, "
        f"{len(coco['videos'])} videos, "
        f"{len(coco['tracks'])} tracks, "
        f"{len(coco['categories'])} categories "
        f"to {output_json}"
    )


def main() -> None:
    configure_fiftyone()
    args = _parse_args()

    dataset_name = args.dataset_name
    logger.info(f"Loading FiftyOne dataset '{dataset_name}' ...")
    try:
        dataset = cast(fo.Dataset, fo.load_dataset(name=dataset_name))
    except Exception as e:
        logger.error(f"Failed to load dataset '{dataset_name}': {e}")
        return

    dataset = dataset.match_tags(f"v:{args.version}")
    if dataset.count() == 0:
        logger.error(f"No samples with version '{args.version}' in dataset '{dataset_name}'")
        return
    logger.info(f"Filtered to {dataset.count()} samples with version '{args.version}'")

    export_fiftyone_to_extended_coco(
        dataset=dataset,
        output_json=args.output_path,
        classes=args.classes,
        images_dir=args.images_dir,
        version=args.version,
        include_labels=parse_label_filters(args.include_labels),
        exclude_labels=parse_label_filters(args.exclude_labels),
        exclude_tags=args.exclude_tags,
        include_tags=args.include_tags,
        label_field=args.label_field,
    )


if __name__ == "__main__":
    main()
