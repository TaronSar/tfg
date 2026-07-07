from __future__ import annotations

import datetime
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger


def load_coco_json(path: str | Path) -> dict[str, Any]:
    """Load a COCO JSON file.

    Args:
        path: Path to the JSON file.

    Returns:
        Parsed COCO dictionary.
    """
    with open(path) as f:
        return json.load(f)


def load_coco_metadata(
    annotations_path: str | Path,
    predictions_path: str | Path,
) -> tuple[dict[int, str], dict[int, dict], dict[int, list]]:
    """Load COCO annotations and predictions, returning parsed metadata.

    Args:
        annotations_path: Path to the COCO annotations JSON.
        predictions_path: Path to the COCO predictions JSON.

    Returns:
        categories: ``category_id → class_name`` mapping.
        images_info: ``image_id → image metadata dict``.
        preds_by_image: ``image_id → list of prediction dicts``.
    """
    coco_ann = load_coco_json(annotations_path)
    categories = {c["id"]: c["name"] for c in coco_ann.get("categories", [])}
    images_info = {img["id"]: img for img in coco_ann.get("images", [])}
    logger.info(f"Categories: {categories}")

    raw_preds: list[dict[str, Any]]
    with open(predictions_path) as f:
        raw_preds = json.load(f)
    logger.info(f"Loaded {len(raw_preds)} predictions from {predictions_path}")

    preds_by_image: dict[int, list] = defaultdict(list)
    for pred in raw_preds:
        preds_by_image[pred["image_id"]].append(pred)

    return categories, images_info, preds_by_image


def save_coco_json(coco: dict[str, Any], path: str | Path, indent: int | None = None) -> None:
    """Save a COCO dictionary to a JSON file, creating parent dirs as needed.

    Args:
        coco: COCO dictionary to save.
        path: Destination file path.
        indent: JSON indentation level (``None`` for compact output).
    """
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(coco, f, indent=indent)


def build_categories(
    classes: list[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Build COCO categories from a list of class names.

    Args:
        classes: Ordered class names. IDs are assigned sequentially from 1.

    Returns:
        ``(categories, name_to_id)`` — list of COCO category dicts and a
        name→ID mapping.
    """
    categories: list[dict[str, Any]] = []
    name_to_id: dict[str, int] = {}
    for cat_id, name in enumerate(classes, start=1):
        name_to_id[name] = cat_id
        categories.append({"id": cat_id, "name": name, "supercategory": "object"})
    return categories, name_to_id


def get_or_add_category(
    name: str,
    name_to_id: dict[str, int],
    categories: list[dict[str, Any]],
) -> int:
    """Return the COCO category ID for *name*, registering it if new.

    Args:
        name: Category label.
        name_to_id: ``{name: coco_id}`` mapping (mutated in place).
        categories: ``coco["categories"]`` list (mutated in place).

    Returns:
        COCO category ID.
    """
    if name not in name_to_id:
        cat_id = len(name_to_id) + 1
        name_to_id[name] = cat_id
        categories.append({"id": cat_id, "name": name, "supercategory": "object"})
    return name_to_id[name]


def build_coco_skeleton(
    version: str = "",
    categories: list[dict[str, Any]] | None = None,
    description: str = "Airborne Tracking Dataset COCO version",
) -> dict[str, Any]:
    """Return a COCO dict with info header and empty collection lists.

    Args:
        version: Version string for ``info.version``.
        categories: Pre-built category list. Empty list when ``None``.
        description: Dataset description for ``info.description``.

    Returns:
        COCO dictionary with all standard top-level keys.
    """
    return {
        "info": {
            "description": description,
            "version": version,
            "license": ["Original dataset license applies. "],
            "url": "",
            "date_created": datetime.datetime.now().isoformat(),
        },
        "licenses": [],
        "images": [],
        "annotations": [],
        "categories": list(categories) if categories else [],
        "videos": [],
        "tracks": [],
    }


def log_coco_stats(coco: dict[str, Any], label: str = "Dataset") -> None:
    """Log standard COCO dataset statistics.

    Args:
        coco: COCO dictionary.
        label: Descriptive prefix for the log line.
    """
    n_img = len(coco.get("images", []))
    n_ann = len(coco.get("annotations", []))
    n_vid = len(coco.get("videos", []))
    n_trk = len(coco.get("tracks", []))
    parts = [f"{n_img} images", f"{n_ann} annotations"]
    if n_vid:
        parts.append(f"{n_vid} videos")
    if n_trk:
        parts.append(f"{n_trk} tracks")
    logger.info(f"{label}: {', '.join(parts)}")
