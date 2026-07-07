import argparse
import json
import math
import re
from typing import Any

from loguru import logger
from tqdm import tqdm

from src.preprocessing.utils.coco_json_io import (
    build_categories,
    build_coco_skeleton,
    get_or_add_category,
    save_coco_json,
)


def _infer_category(track_id: str) -> str:
    """Infer category name from track ID.

    Uses common patterns in the dataset (e.g. Airborne1 -> airborne,
    Helicopter1 -> helicopter).

    Args:
        track_id: Raw track identifier string from the dataset.

    Returns:
        Inferred category name.
    """
    class_name = re.sub(r"\d+$", "", track_id).strip().lower()
    return class_name if class_name else "unknown"


def _get_or_add_track(
    video_id: int,
    raw_track_id: str,
    category_id: int,
    track_id_map: dict[tuple[int, str], int],
    tracks: list[dict[str, Any]],
    next_track_id: int,
) -> tuple[int, int]:
    """Return the COCO track ID for *(video_id, raw_track_id)*, creating it if new.

    Args:
        video_id: COCO video ID for the current video.
        raw_track_id: Raw track identifier from the source dataset.
        category_id: COCO category ID for this track.
        track_id_map: ``{(video_id, raw_track_id): coco_track_id}`` (mutated).
        tracks: ``coco["tracks"]`` list (mutated in place).
        next_track_id: Next available COCO track ID counter.

    Returns:
        ``(coco_track_id, updated_next_track_id)`` tuple.
    """
    key = (video_id, raw_track_id)
    if key not in track_id_map:
        track_id_map[key] = next_track_id
        tracks.append({"id": next_track_id, "category_id": category_id, "video_id": video_id})
        next_track_id += 1
    return track_id_map[key], next_track_id


def convert_airborne_to_coco(
    annotations_file: str,
    output_json: str,
    version: str = "1.0",
    classes: list[str] | None = None,
) -> None:
    """Convert Airborne Object Tracking annotations to COCO format.

    Parses the proprietary AOT JSON schema and writes a COCO JSON file
    to *output_json*.

    The output extends the standard COCO schema with:

    * ``videos``  — per-video metadata (path, resolution, fps, frame count).
    * ``tracks``  — per-track metadata linking categories to videos.

    Args:
        annotations_file: Path to the raw AOT annotation JSON file.
        output_json: Destination path for the output COCO JSON file.
        version: Version string embedded in ``coco["info"]["version"]``.
        classes: Ordered class names for category IDs.  When ``None``,
            categories are inferred from track IDs in the data.
    """
    if classes is not None:
        categories, category_map = build_categories(classes)
    else:
        categories, category_map = [], {}

    coco = build_coco_skeleton(version=version, categories=categories)

    unique_image_paths: set[str] = set()
    image_id_map: dict[str, int] = {}  # image_path --> coco image_id
    video_map: dict[str, int] = {}  # flight_id  --> coco video_id
    track_id_map: dict[tuple[int, str], int] = {}  # (video_id, raw_id) --> coco track_id

    image_id = 1
    annotation_id = 1
    video_id = 1
    track_id = 1
    with open(annotations_file) as f:
        data = json.load(f)

    samples = data.get("samples", {})
    if not isinstance(samples, dict):
        logger.error(f"Expected 'samples' to be a dict, got {type(samples)}")
        return

    for flight_id, sample in tqdm(samples.items(), desc="Converting samples", unit="flight"):
        metadata = sample.get("metadata", {})
        frames = sample.get("entities", [])
        width = metadata.get("resolution", {}).get("width")
        height = metadata.get("resolution", {}).get("height")

        video_path = metadata.get("data_path")
        if video_path is None:
            logger.warning(f"Missing data_path for flight {flight_id}, skipping")
            continue
        video_path = video_path.split("/", 1)[1]  # Fix path to remove "trainX" directory

        current_video_id = video_id
        coco["videos"].append(
            {
                "id": current_video_id,
                "file_name": video_path,
                "width": width,
                "height": height,
                "fps": metadata.get("fps"),
                "num_frames": metadata.get("number_of_frames"),
            }
        )
        video_map[flight_id] = current_video_id
        video_id += 1

        for frame in frames:
            img_name = frame.get("img_name")
            if img_name is None:
                logger.warning(f"Missing img_name in frame for flight {flight_id}, skipping frame")
                continue

            image_path = video_path + img_name
            if image_path not in unique_image_paths:
                unique_image_paths.add(image_path)
                image_id_map[image_path] = image_id
                coco["images"].append(
                    {
                        "id": image_id,
                        "width": width,
                        "height": height,
                        "file_name": image_path,
                        "video_id": current_video_id,
                        "frame_id": frame.get("blob").get("frame"),
                    }
                )
                image_id += 1

            bbox = frame.get("bb", [])
            if not bbox:
                continue

            if len(bbox) != 4 or bbox[2] <= 0 or bbox[3] <= 0:
                logger.warning(
                    f"Invalid bbox {bbox} in frame for flight {flight_id}, skipping annotation"
                )
                continue

            raw_track_id = frame.get("id")
            category_name = _infer_category(raw_track_id)
            category_id = get_or_add_category(category_name, category_map, coco["categories"])
            coco_track_id, track_id = _get_or_add_track(
                current_video_id,
                raw_track_id,
                category_id,
                track_id_map,
                coco["tracks"],
                track_id,
            )

            range_m = frame.get("blob", {}).get("range_distance_m", -1.0)
            if math.isnan(range_m):
                range_m = -1.0

            coco["annotations"].append(
                {
                    "id": annotation_id,
                    "category_id": category_id,
                    "iscrowd": 0,
                    "segmentation": [],
                    "image_id": image_id_map[image_path],
                    "area": bbox[2] * bbox[3],
                    "bbox": bbox,
                    "track_id": coco_track_id,
                    "range_m": range_m,
                    "is_above_horizon": frame.get("labels", {}).get("is_above_horizon", -1),
                }
            )
            annotation_id += 1

    save_coco_json(coco, output_json, indent=2)

    logger.info(f"COCO annotations saved to {output_json}")


def main():
    parser = argparse.ArgumentParser(
        description="Convert Airborne Object Tracking annotations to COCO format."
    )
    parser.add_argument(
        "--annotations_file",
        required=True,
        help="File containing airborne JSON annotations",
    )
    parser.add_argument(
        "--output_json",
        required=True,
        help="Output COCO annotation file path",
    )
    parser.add_argument("--version", required=False, help="Dataset version")
    parser.add_argument(
        "--classes",
        nargs="+",
        default=None,
        help="Ordered class names for category IDs (default: infer from data)",
    )
    args = parser.parse_args()

    convert_airborne_to_coco(
        args.annotations_file, args.output_json, args.version, classes=args.classes
    )


if __name__ == "__main__":
    main()
