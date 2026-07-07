"""Reusable COCO evaluation metrics."""
from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

from loguru import logger
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval
from tqdm import tqdm

from src.ood.common.transforms import CORRUPTIONS, SEVERITIES


def f1_from_map_ar(coco_eval: COCOeval) -> float:
    """Compute F1 as the harmonic mean of mAP and AR@100.

    This matches the ``bbox_F1`` metric produced by
    ``AirborneCocoMetric`` in ``sw_ai_detection``:
    ``F1 = 2 * mAP * AR@100 / (mAP + AR@100)``.

    Both mAP (``stats[0]``) and AR@100 (``stats[8]``) are computed at
    IoU=0.50:0.95, so the F1 inherits the same IoU range.

    Args:
        coco_eval: A fully evaluated and accumulated ``COCOeval`` object.

    Returns:
        F1 score, or 0.0 when mAP + AR is zero.
    """
    mAP = float(coco_eval.stats[0])  # AP  @ IoU=0.50:0.95, area=all, maxDets=100
    ar = float(coco_eval.stats[8])  # AR  @ IoU=0.50:0.95, area=all, maxDets=100
    if mAP + ar > 0:
        return 2.0 * mAP * ar / (mAP + ar)
    return 0.0


def eval_coco_subset(
    coco_gt: COCO,
    coco_dt: COCO,
    image_ids: list[int],
) -> tuple[float, float]:
    """Run COCOeval on a subset of images and return (mAP, F1).

    Args:
        coco_gt: Ground-truth COCO object.
        coco_dt: Detection results COCO object.
        image_ids: COCO image IDs to evaluate.

    Returns:
        A 2-tuple ``(mAP, F1)`` where *mAP* is AP @ IoU=0.50:0.95
        and *F1* is ``2 * mAP * AR@100 / (mAP + AR@100)``.
    """
    coco_eval = COCOeval(coco_gt, coco_dt, "bbox")
    coco_eval.params.imgIds = image_ids
    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()
    mAP = float(coco_eval.stats[0])
    f1 = f1_from_map_ar(coco_eval)
    return mAP, f1


def compute_grouped_map(
    coco_json_path: Path,
    predictions_path: Path,
    mapping_path: Path,
    *,
    variant_tag_fn: object = None,
) -> dict:
    """Compute mAP and F1 per (corruption, severity) group.

    F1 is the harmonic mean of mAP and AR@100 (both at IoU=0.50:0.95),
    matching the ``bbox_F1`` definition in ``sw_ai_detection``.

    Args:
        coco_json_path: Path to the combined COCO ground-truth JSON.
        predictions_path: Path to ``predictions.bbox.json``.
        mapping_path: Path to ``image_id_mapping.json`` that maps each
            new image ID to ``(variant_tag, original_id)``.
        variant_tag_fn: Callable ``(corruption, severity) -> str`` used
            to build variant tags.  Defaults to ``"<corruption>_<severity>"``
            or ``"clean"`` when *corruption* is ``None``.

    Returns:
        Dict with ``"clean_mAP"``, ``"clean_f1"``, and ``"results"``
        keyed by corruption type and severity level.  Each severity entry
        contains ``mAP``, ``relative_mAP``, ``f1``, and ``relative_f1``.
    """
    if variant_tag_fn is None:
        def variant_tag_fn(corruption, severity):
            if corruption is None:
                return "clean"
            return f"{corruption}_{severity}"

    with open(mapping_path, encoding="utf-8") as f:
        raw_mapping = json.load(f)
    id_to_variant = {int(k): tuple(v) for k, v in raw_mapping.items()}

    variant_to_ids: dict[str, list[int]] = defaultdict(list)
    for img_id, (variant, _orig_id) in id_to_variant.items():
        variant_to_ids[variant].append(img_id)

    coco_gt = COCO(str(coco_json_path))
    coco_dt = coco_gt.loadRes(str(predictions_path))

    clean_ids = variant_to_ids.get("clean", [])
    clean_map, clean_f1 = eval_coco_subset(coco_gt, coco_dt, clean_ids) if clean_ids else (0.0, 0.0)
    logger.info(f"Clean baseline mAP: {clean_map:.4f}  F1: {clean_f1:.4f}")

    results: dict[str, dict[str, dict[str, float]]] = {}
    pairs = [(c, s) for c in CORRUPTIONS for s in SEVERITIES]
    for corruption, severity in tqdm(pairs, desc="Computing metrics", unit="group"):
        if corruption not in results:
            results[corruption] = {}
        tag = variant_tag_fn(corruption, severity)
        ids = variant_to_ids.get(tag, [])
        if not ids:
            results[corruption][str(severity)] = {
                "mAP": 0.0,
                "relative_mAP": 0.0,
                "f1": 0.0,
                "relative_f1": 0.0,
            }
            continue
        mAP, f1 = eval_coco_subset(coco_gt, coco_dt, ids)
        rel_map = mAP / clean_map if clean_map > 0 else 0.0
        rel_f1 = f1 / clean_f1 if clean_f1 > 0 else 0.0
        results[corruption][str(severity)] = {
            "mAP": round(mAP, 6),
            "relative_mAP": round(rel_map, 6),
            "f1": round(f1, 6),
            "relative_f1": round(rel_f1, 6),
        }
        logger.info(
            f"  {tag}: mAP={mAP:.4f}  rel_mAP={rel_map:.4f}  F1={f1:.4f}  rel_F1={rel_f1:.4f}"
        )

    return {
        "clean_mAP": round(clean_map, 6),
        "clean_f1": round(clean_f1, 6),
        "results": results,
    }
