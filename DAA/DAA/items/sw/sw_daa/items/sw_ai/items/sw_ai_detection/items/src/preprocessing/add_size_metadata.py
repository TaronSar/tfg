import argparse
from typing import Any

from loguru import logger

from src.preprocessing.utils.coco_json_io import load_coco_json, log_coco_stats, save_coco_json


def add_size_metadata(
    coco: dict[str, Any], small_threshold: int, medium_threshold: int
) -> dict[str, Any]:
    """Add ``size_category`` and ``area`` fields to each annotation.

    Args:
        coco: COCO dict with ``annotations``.
        small_threshold: Max area (pixels²) for the *small* category.
        medium_threshold: Max area (pixels²) for the *medium* category.

    Returns:
        The same *coco* dict, modified in place.

    Raises:
        ValueError: If *small_threshold* >= *medium_threshold*.
    """
    if small_threshold >= medium_threshold:
        raise ValueError(
            f"small_threshold ({small_threshold}) must be less"
            f" than medium_threshold ({medium_threshold})"
        )
    for ann in coco.get("annotations", []):
        _, _, width, height = ann["bbox"]
        ann["area"] = float(width) * float(height)
        if ann["area"] <= small_threshold:
            ann["size_category"] = "small"
        elif ann["area"] <= medium_threshold:
            ann["size_category"] = "medium"
        else:
            ann["size_category"] = "large"
    return coco


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    p = argparse.ArgumentParser(
        description=("Add size metadata to annotations in a COCO dataset. "),
    )
    p.add_argument("--input-json", required=True, help="Path to input COCO JSON.")
    p.add_argument("--output-json", required=True, help="Path for the output COCO JSON.")
    p.add_argument(
        "--small-threshold",
        required=True,
        type=int,
        help="Pixel area threshold for small objects (in pixels).",
    )
    p.add_argument(
        "--medium-threshold",
        required=True,
        type=int,
        help="Pixel area threshold for medium objects (in pixels).",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    coco = load_coco_json(args.input_json)
    log_coco_stats(coco, "Loaded")

    coco = add_size_metadata(
        coco, small_threshold=args.small_threshold, medium_threshold=args.medium_threshold
    )

    save_coco_json(coco, args.output_json)
    logger.info(f"Written {args.output_json}")


if __name__ == "__main__":
    main()
