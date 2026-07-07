"""Evaluate detection performance under image corruptions.

Stage 07 of the OOD pipeline.  Consumes crops that already exist in storage:

* clean crops from the detection ``airborne_cropped_images/`` tree, indexed by
  the curated ``<split>_crops.json`` produced by stage 04, and
* corrupted crops from ``airborne_corrupted_images/cropped/``, indexed by the
  ``<split>_crops.json`` produced by stage 06.

Both COCO JSONs are merged into a single ``combined_coco.json`` whose
``file_name`` fields are *absolute* paths (the image storage is mounted at the
same path inside the container), so no crops are re-extracted or copied.  YOLOX inference
runs once via Docker; per-(corruption, severity) mAP and F1 (harmonic mean of mAP and AR@100,
matching ``sw_ai_detection``) are computed with pycocotools and plotted.  A
per-crop GT/prediction JSONL is exported for the FiftyOne crops dataset.

Output::

    <output_dir>/reports/detection_degradation_results.json
    <output_dir>/reports/detection_degradation_bar.png
    <output_dir>/reports/detection_degradation_heatmap.png
    <output_dir>/reports/detection_degradation_f1_bar.png
    <output_dir>/reports/detection_degradation_f1_heatmap.png
    <output_dir>/reports/recommended_ood_filter.txt
    <output_dir>/reports/detection_samples.crops.jsonl

Usage::

    PYTHONPATH=. uv run python scripts/evaluate_detection_degradation.py \\
        --clean_crops_json data/04_apply_curation/test_crops.json \\
        --corrupted_crops_json data/06_create_corrupted_crops/test_crops.json \\
        --clean_crops_img_dir /mnt/Pool_IA/.../airborne_cropped_images \\
        --corrupted_crops_img_dir /mnt/Pool_IA/.../airborne_corrupted_images/cropped \\
        --checkpoint_path ../../sw_ai_detection/items/models/best_coco_bbox_mAP_epoch_38.pth \\
        --config_path ../../sw_ai_detection/items/configs/experiments/yolox_tiny_airborne.py \\
        --sw_ai_detection_root ../../sw_ai_detection/items
"""

from __future__ import annotations

import json
from pathlib import Path

import fire
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

from src.ood.common.config_loader import load_paths_config
from src.ood.common.coco_utils import (
    build_combined_coco,
    export_detection_crops,
    variant_tag,
)
from src.ood.evaluation.coco_metrics import compute_grouped_map
from src.ood.evaluation.detection_degradation import plot_degradation

from scripts.run_detection_model import run_yolox_docker


def evaluate_detection_degradation(
    clean_crops_json: str,
    corrupted_crops_json: str,
    clean_crops_img_dir: str,
    corrupted_crops_img_dir: str,
    checkpoint_path: str,
    config_path: str,
    sw_ai_detection_root: str,
    output_dir: str | None = None,
    work_dir: str | None = None,
    threshold: float = 0.80,
) -> None:
    """Orchestrate detection inference on persisted crops, metrics and plotting.

    Stage 07 of the OOD pipeline.  Merges the curated clean crops (stage 04)
    and corrupted crops (stage 06) into a single COCO JSON whose ``file_name``
    fields are absolute paths, runs YOLOX inference once via Docker,
    computes per-(corruption, severity) mAP and F1 (harmonic mean of mAP and
    AR@100), exports a per-crop GT/prediction JSONL for the FiftyOne crops
    dataset, and generates the degradation plots + recommended OOD filter.

    Args:
        clean_crops_json: Path to the curated clean crops COCO JSON
            (``<split>_crops.json`` from stage 04).
        corrupted_crops_json: Path to the corrupted crops COCO JSON
            (``<split>_crops.json`` from stage 06).
        clean_crops_img_dir: Root of the clean crops tree (the
            detection ``airborne_cropped_images/`` directory).
        corrupted_crops_img_dir: Root of the corrupted crops tree.
        checkpoint_path: Path to the YOLOX ``.pth`` checkpoint.
        config_path: Path to the MMEngine experiment config.
        sw_ai_detection_root: Path to ``sw_ai_detection/items/``.
        output_dir: Directory for results JSON, plots, and the per-crop JSONL.
        work_dir: Scratch directory for the combined COCO + predictions.
        threshold: Relative mAP threshold for the recommended OOD filter.
    """
    paths_cfg = load_paths_config()
    base_deg_dir = Path(paths_cfg["detection_degradation_dir"])
    output_dir = output_dir or str(base_deg_dir / "reports")
    work_dir = work_dir or str(base_deg_dir / "work")

    clean_json = Path(clean_crops_json)
    corrupted_json = Path(corrupted_crops_json)
    clean_img_dir = Path(clean_crops_img_dir)
    corrupted_img_dir = Path(corrupted_crops_img_dir)
    ckpt = Path(checkpoint_path)
    config = Path(config_path)
    det_root = Path(sw_ai_detection_root)
    out = Path(output_dir)
    work = Path(work_dir)

    work.mkdir(parents=True, exist_ok=True)
    out.mkdir(parents=True, exist_ok=True)

    # Step 1: Load persisted clean + corrupted crops COCO JSONs
    logger.info(f"Loading clean crops COCO: {clean_json}")
    with open(clean_json, encoding="utf-8") as f:
        clean_coco = json.load(f)
    logger.info(f"  {len(clean_coco['images'])} clean crops")

    logger.info(f"Loading corrupted crops COCO: {corrupted_json}")
    with open(corrupted_json, encoding="utf-8") as f:
        corrupted_coco = json.load(f)
    logger.info(f"  {len(corrupted_coco['images'])} corrupted crops")

    # Step 2: Build combined COCO with absolute paths
    logger.info("Building combined COCO JSON …")
    coco_path, mapping_path, meta = build_combined_coco(
        clean_coco,
        corrupted_coco,
        clean_img_dir,
        corrupted_img_dir,
        work,
    )

    # Step 3: Run detection model on absolute crop paths (no copying)
    pred_path = run_yolox_docker(det_root, work, config, ckpt, image_prefix="")

    # Step 4: Compute per-group mAP and F1
    logger.info("Computing per-group mAP and F1 …")
    results = compute_grouped_map(
        coco_path, pred_path, mapping_path, variant_tag_fn=variant_tag,
    )

    # Step 5: Write results JSON
    results_path = out / "detection_degradation_results.json"
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    logger.info(f"Results written to {results_path}")

    # Step 6: Export per-crop GT/predictions for the FiftyOne crops dataset
    export_detection_crops(
        coco_path,
        pred_path,
        meta,
        out / "detection_samples.crops.jsonl",
    )

    # Step 7: Generate plots + recommended OOD filter
    logger.info("Generating plots …")
    rec = plot_degradation(results_path, out, threshold=threshold)
    logger.info(f"Recommended ood_filter: {rec}")
    logger.info("Done.")


def main(
    clean_crops_json: str,
    corrupted_crops_json: str,
    clean_crops_img_dir: str,
    corrupted_crops_img_dir: str,
    checkpoint_path: str,
    config_path: str,
    sw_ai_detection_root: str,
    output_dir: str | None = None,
    work_dir: str | None = None,
    threshold: float = 0.80,
) -> None:
    """CLI entry point — delegates to :func:`evaluate_detection_degradation`."""
    evaluate_detection_degradation(
        clean_crops_json=clean_crops_json,
        corrupted_crops_json=corrupted_crops_json,
        clean_crops_img_dir=clean_crops_img_dir,
        corrupted_crops_img_dir=corrupted_crops_img_dir,
        checkpoint_path=checkpoint_path,
        config_path=config_path,
        sw_ai_detection_root=sw_ai_detection_root,
        output_dir=output_dir,
        work_dir=work_dir,
        threshold=threshold,
    )


if __name__ == "__main__":
    fire.Fire(main)
