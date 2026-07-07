from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np
from cleanlab.object_detection.filter import find_label_issues as find_label_issues_cleanlab
from cleanlab.object_detection.rank import get_label_quality_scores
from loguru import logger

from src.preprocessing.utils.coco_json_io import load_coco_json, load_coco_metadata


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Find label issues in a COCO dataset using cleanlab",
    )
    parser.add_argument(
        "--annotations-path",
        required=True,
        help="Path to COCO annotations JSON (e.g. data/06_split/train.json)",
    )
    parser.add_argument(
        "--predictions-path",
        required=True,
        help="Path to COCO predictions JSON (*.bbox.json)",
    )
    parser.add_argument(
        "--output-path",
        required=True,
        help="Path for the output JSON report",
    )
    return parser.parse_args()


def _build_category_index(categories: dict[int, str]) -> tuple[dict[int, int], int]:
    """Map COCO 1-indexed category IDs to 0-indexed cleanlab class indices.

    Args:
        categories: Mapping from COCO category_id to category name.

    Returns:
        cat_id_to_idx: mapping from COCO category_id to 0-based index.
        num_classes: total number of classes.
    """
    cat_ids = sorted(categories.keys())
    return {cid: idx for idx, cid in enumerate(cat_ids)}, len(cat_ids)


def _group_annotations_by_image(
    annotations: list[dict],
) -> dict[int, list[dict]]:
    """Group COCO annotations by image_id.

    Args:
        annotations: List of COCO annotation dicts.

    Returns:
        Mapping from image_id to list of annotation dicts for that image.
    """
    by_image: dict[int, list[dict]] = defaultdict(list)
    for ann in annotations:
        by_image[ann["image_id"]].append(ann)
    return by_image


def _convert_labels(
    anns: list[dict],
    cat_id_to_idx: dict[int, int],
) -> dict[str, np.ndarray]:
    """Convert COCO annotations for one image to cleanlab label dict.

    Args:
        anns: List of COCO annotation dicts for one image.
        cat_id_to_idx: Mapping from COCO category_id to 0-based class index.

    Returns:
        Dict with keys "bboxes" (float array of shape (M, 4)) and "labels" (int array of shape (M,))
    """
    bboxes = []
    labs = []
    for a in anns:
        x, y, w, h = a["bbox"]
        bboxes.append([x, y, x + w, y + h])
        labs.append(cat_id_to_idx[a["category_id"]])
    return {
        "bboxes": np.array(bboxes, dtype=np.float64).reshape(-1, 4),
        "labels": np.array(labs, dtype=np.intp),
    }


def _convert_predictions(
    preds: list[dict],
    cat_id_to_idx: dict[int, int],
    num_classes: int,
) -> np.ndarray:
    """Convert COCO predictions for one image to cleanlab prediction array.

    Args:
        preds: List of COCO prediction dicts for one image.
        cat_id_to_idx: Mapping from COCO category_id to 0-based class index.
        num_classes: Total number of classes.

    Returns:
        An object array of shape ``(num_classes,)`` where each element is
        an ``(M, 5)`` float array of ``[x1, y1, x2, y2, score]``.
    """
    per_class: list[list[list[float]]] = [[] for _ in range(num_classes)]
    for p in preds:
        idx = cat_id_to_idx.get(p["category_id"])
        if idx is None:
            continue
        x, y, w, h = p["bbox"]
        per_class[idx].append([x, y, x + w, y + h, float(p["score"])])

    pred_array = np.empty(num_classes, dtype=object)
    for k in range(num_classes):
        if per_class[k]:
            pred_array[k] = np.array(per_class[k], dtype=np.float64)
        else:
            pred_array[k] = np.zeros((0, 5), dtype=np.float64)
    return pred_array


def build_cleanlab_inputs(
    categories: dict[int, str],
    images_info: dict[int, dict],
    preds_by_image: dict[int, list],
    coco_annotations: list[dict],
) -> tuple[list[int], list[dict], list[np.ndarray]]:
    """Convert full COCO dataset into the list format expected by cleanlab.

    Args:
        categories: Mapping from COCO category_id to category name.
        images_info: Mapping from image ID to image metadata dict.
        preds_by_image: Mapping from image ID to list of prediction dicts.
        coco_annotations: List of COCO annotation dicts.

    Returns:
        image_ids: ordered list of image IDs (for mapping results back).
        labels: list of label dicts, one per image.
        predictions: list of prediction arrays, one per image.
    """
    cat_id_to_idx, num_classes = _build_category_index(categories)
    ann_by_image = _group_annotations_by_image(coco_annotations)
    image_ids = sorted(images_info.keys())

    labels_list = [_convert_labels(ann_by_image.get(iid, []), cat_id_to_idx) for iid in image_ids]
    predictions_list = [
        _convert_predictions(preds_by_image.get(iid, []), cat_id_to_idx, num_classes)
        for iid in image_ids
    ]
    return image_ids, labels_list, predictions_list


def build_report(
    image_ids: list[int],
    images_info: dict[int, dict],
    scores: np.ndarray,
    issue_indices: np.ndarray,
) -> dict:
    """Build a JSON-serializable report from cleanlab results.

    Args:
        image_ids: List of image IDs corresponding to the scores.
        images_info: Mapping from image ID to image metadata dict (must include "file_name").
        scores: Array of quality scores for each image.
        issue_indices: Indices of images flagged as issues by cleanlab.

    Returns:
        Report dict with overall stats and per-image details.
    """
    is_issue = np.zeros(len(scores), dtype=bool)
    is_issue[issue_indices] = True

    return {
        "num_images": len(image_ids),
        "num_issues": int(is_issue.sum()),
        "images": [
            {
                "image_id": int(image_ids[i]),
                "file_name": images_info[image_ids[i]].get("file_name", ""),
                "quality_score": float(scores[i]),
                "is_issue": bool(is_issue[i]),
            }
            for i in range(len(image_ids))
        ],
    }


def write_report(report: dict, output_path: str | Path) -> None:
    """Write the report dict to a JSON file.

    Args:
        report: Report dict to write.
        output_path: Destination file path for the JSON report.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    logger.info(
        f"Report written to {out}: {report['num_issues']}/{report['num_images']} images flagged"
    )


def find_label_issues(
    coco_annotations_path: str,
    predictions_path: str,
    output_report_path: str,
) -> None:
    """Main entry point to find label issues in a COCO dataset using cleanlab.

    Args:
        coco_annotations_path: Path to COCO annotations JSON (e.g. data/06_split/train.json).
        coco_predictions_path: Path to COCO predictions JSON (*.bbox.json).
        output_report_path: Path for the output JSON report.
    """
    coco_dataset = load_coco_json(coco_annotations_path)

    categories, images_info, preds_by_image = load_coco_metadata(
        coco_annotations_path,
        predictions_path,
    )
    logger.info(
        f"Loaded {len(images_info)} images, "
        f"{len(coco_dataset['annotations'])} annotations, "
        f"{sum(len(v) for v in preds_by_image.values())} predictions"
    )

    image_ids, labels_list, predictions_list = build_cleanlab_inputs(
        categories,
        images_info,
        preds_by_image,
        coco_dataset["annotations"],
    )

    logger.info("Computing label quality scores...")
    scores = get_label_quality_scores(labels_list, predictions_list)

    logger.info("Finding label issues...")
    issue_indices = find_label_issues_cleanlab(
        labels_list,
        predictions_list,
        return_indices_ranked_by_score=True,
    )

    report = build_report(image_ids, images_info, scores, issue_indices)
    write_report(report, output_report_path)


def main() -> None:
    args = _parse_args()

    find_label_issues(
        coco_annotations_path=args.annotations_path,
        predictions_path=args.predictions_path,
        output_report_path=args.output_path,
    )


if __name__ == "__main__":
    main()
