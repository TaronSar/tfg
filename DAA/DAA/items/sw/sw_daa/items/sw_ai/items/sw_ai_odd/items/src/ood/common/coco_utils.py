"""COCO I/O utilities shared across OOD pipeline scripts."""
from __future__ import annotations

import json
from collections import defaultdict
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from src.ood.common.io import write_jsonl
from src.ood.common.path_utils import crop_to_frame_path, parse_crop_offset


def crop_offset_from_entry(img_entry: dict) -> tuple[int, int]:
    """Return the ``(x0, y0)`` crop offset for a COCO crop image entry.

    Prefers the explicit ``crop_x``/``crop_y`` fields written by the detection
    pipeline, falling back to parsing the ``_x_<X>_y_<Y>`` filename suffix.

    Args:
        img_entry: COCO image entry from a detection crops JSON.

    Returns:
        ``(x0, y0)`` integer pixel offsets.
    """
    if "crop_x" in img_entry and "crop_y" in img_entry:
        return int(img_entry["crop_x"]), int(img_entry["crop_y"])
    return parse_crop_offset(img_entry["file_name"])


def variant_tag(corruption: str | None, severity: int | None) -> str:
    """Return a filesystem-safe variant name.

    Args:
        corruption: Corruption type name, or ``None`` for clean.
        severity: Severity level, or ``None`` for clean.

    Returns:
        Tag string like ``"fog_3"`` or ``"clean"``.
    """
    if corruption is None:
        return "clean"
    return f"{corruption}_{severity}"


def parse_variant(tag: str) -> tuple[str | None, int | None]:
    """Decode a variant tag back to corruption metadata.

    Args:
        tag: Variant tag produced by :func:`variant_tag`.

    Returns:
        Tuple ``(corruption_type, severity)``.  For ``"clean"`` returns
        ``(None, None)``.
    """
    if tag == "clean":
        return None, None
    corruption, sev = tag.rsplit("_", 1)
    return corruption, int(sev)


def build_combined_coco(
    clean_coco: dict,
    corrupted_coco: dict,
    clean_crops_dir: Path,
    corrupted_crops_dir: Path,
    work_dir: Path,
    variant_of_corrupted: Callable[[dict], str] | None = None,
) -> tuple[Path, Path, dict[int, dict]]:
    """Merge persisted clean and corrupted crops into one COCO JSON.

    Image ``file_name`` fields are rewritten to *absolute* paths so the
    detector reads each crop directly.  Each crop gets a fresh,
    globally-unique image ID; the clean crops are tagged ``"clean"`` and the
    corrupted crops are tagged via *variant_of_corrupted*.

    Args:
        clean_coco: Curated clean crops COCO dict, with ``file_name`` relative
            to *clean_crops_dir*.
        corrupted_coco: Corrupted crops COCO dict, with ``file_name`` relative
            to *corrupted_crops_dir* and per-image
            ``corruption_type``/``corruption_severity``/``source_frame`` fields.
        clean_crops_dir: Root of the clean crops tree.
        corrupted_crops_dir: Root of the corrupted crops tree.
        work_dir: Scratch directory where the combined JSON and ID mapping are
            written.
        variant_of_corrupted: Optional callable ``(img_entry) -> variant_str``
            for corrupted images.  Defaults to
            ``variant_tag(img["corruption_type"], img["corruption_severity"])``.

    Returns:
        Tuple ``(coco_path, mapping_path, meta)`` where *meta* maps each new
        image ID to ``{variant, filepath, crop_x, crop_y, source_frame,
        width, height}``.
    """
    if variant_of_corrupted is None:
        variant_of_corrupted = lambda img: variant_tag(  # noqa: E731
            img.get("corruption_type"), img.get("corruption_severity")
        )

    combined_images: list[dict] = []
    combined_anns: list[dict] = []
    image_id_to_variant: dict[int, tuple[str, int]] = {}
    meta: dict[int, dict] = {}
    img_id = 1
    ann_id = 1

    def _add(coco: dict, crops_dir: Path, get_variant: Callable[[dict], str]) -> None:
        nonlocal img_id, ann_id
        anns_by_img: dict[int, list[dict]] = defaultdict(list)
        for ann in coco.get("annotations", []):
            anns_by_img[int(ann["image_id"])].append(ann)
        for img in coco["images"]:
            old_id = int(img["id"])
            x0, y0 = crop_offset_from_entry(img)
            abs_path = str((crops_dir / img["file_name"]).absolute())
            var = get_variant(img)
            source_frame = img.get("source_frame") or crop_to_frame_path(img["file_name"])
            new_id = img_id
            img_id += 1
            combined_images.append(
                {
                    "id": new_id,
                    "width": int(img["width"]),
                    "height": int(img["height"]),
                    "file_name": abs_path,
                }
            )
            image_id_to_variant[new_id] = (var, old_id)
            meta[new_id] = {
                "variant": var,
                "filepath": abs_path,
                "crop_x": int(x0),
                "crop_y": int(y0),
                "source_frame": source_frame,
                "width": int(img["width"]),
                "height": int(img["height"]),
            }
            for ann in anns_by_img.get(old_id, []):
                combined_anns.append({**ann, "id": ann_id, "image_id": new_id})
                ann_id += 1

    _add(clean_coco, clean_crops_dir, lambda _img: "clean")
    _add(corrupted_coco, corrupted_crops_dir, variant_of_corrupted)

    combined = {
        "images": combined_images,
        "annotations": combined_anns,
        "categories": clean_coco.get("categories", []),
    }
    coco_path = work_dir / "combined_coco.json"
    with open(coco_path, "w", encoding="utf-8") as f:
        json.dump(combined, f)
    logger.info(
        f"Combined COCO: {len(combined_images)} images, {len(combined_anns)} annotations"
    )

    mapping_path = work_dir / "image_id_mapping.json"
    serializable = {str(k): list(v) for k, v in image_id_to_variant.items()}
    with open(mapping_path, "w", encoding="utf-8") as f:
        json.dump(serializable, f)

    return coco_path, mapping_path, meta


def export_detection_crops(
    combined_coco_path: Path,
    predictions_path: Path,
    meta: dict[int, dict],
    output_path: Path,
) -> None:
    """Export per-crop GT/predicted detections for the FiftyOne crops dataset.

    Bounding boxes are kept in crop-local pixel coordinates (the crop image
    itself is the FiftyOne sample).  Each row carries the corruption metadata
    and the ``source_frame`` so the crops dataset can inherit the parent
    full-image ID/OOD verdict in stage 11.

    Args:
        combined_coco_path: Path to the combined COCO ground-truth JSON.
        predictions_path: Path to ``predictions.bbox.json``.
        meta: ``new_image_id -> {variant, filepath, crop_x, crop_y,
            source_frame, width, height}`` mapping from
            :func:`build_combined_coco`.
        output_path: Destination JSONL path.
    """
    with open(combined_coco_path, encoding="utf-8") as f:
        coco = json.load(f)
    with open(predictions_path, encoding="utf-8") as f:
        preds = json.load(f)

    cat_name = {int(c["id"]): c.get("name", str(c["id"])) for c in coco.get("categories", [])}

    gt_by_img: dict[int, list[dict]] = defaultdict(list)
    for ann in coco.get("annotations", []):
        gt_by_img[int(ann["image_id"])].append(ann)

    pred_by_img: dict[int, list[dict]] = defaultdict(list)
    for pred in preds:
        pred_by_img[int(pred["image_id"])].append(pred)

    rows: list[dict] = []
    for image_id, info in meta.items():
        corruption, severity = parse_variant(info["variant"])
        rows.append(
            {
                "task": "detection_degradation",
                "sample_id": image_id,
                "variant": info["variant"],
                "filepath": info["filepath"],
                "img_name": Path(info["filepath"]).name,
                "source_frame": info["source_frame"],
                "crop_x": info["crop_x"],
                "crop_y": info["crop_y"],
                "image_width": info["width"],
                "image_height": info["height"],
                "corruption_type": corruption,
                "corruption_severity": severity,
                "detection_gt": [
                    {
                        "label": cat_name.get(int(ann["category_id"]), str(ann["category_id"])),
                        "category_id": int(ann["category_id"]),
                        "bbox_abs": [float(v) for v in ann["bbox"]],
                    }
                    for ann in gt_by_img.get(image_id, [])
                ],
                "detection_pred": [
                    {
                        "label": cat_name.get(
                            int(pred["category_id"]), str(pred["category_id"])
                        ),
                        "category_id": int(pred["category_id"]),
                        "bbox_abs": [float(v) for v in pred["bbox"]],
                        "confidence": float(pred.get("score", 0.0)),
                    }
                    for pred in pred_by_img.get(image_id, [])
                ],
            }
        )

    write_jsonl(output_path, rows)
    logger.info(f"Per-crop detection JSONL: {output_path} ({len(rows)} rows)")
