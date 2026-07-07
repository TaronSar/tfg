import argparse
from pathlib import Path, PurePosixPath

from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

import fiftyone as fo
from src.fiftyone._utils import (
    apply_label_filters,
    configure_fiftyone,
    get_version_view,
    launch_fiftyone_app,
    parse_label_filters,
)
from src.preprocessing.utils.coco_json_io import load_coco_metadata

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)


def _save_results(res: object, key: str, out: Path) -> None:
    """Save report JSON, confusion matrix and PR curves for evaluation results."""
    res.write_json(str(out / f"{key}_report.json"))  # type: ignore[attr-defined]
    logger.info(f"Saved report → {out / f'{key}_report.json'}")

    cm_fig = res.plot_confusion_matrix()  # type: ignore[attr-defined]
    cm_fig.save(str(out / f"{key}_confusion_matrix.html"))
    logger.info(f"Saved confusion matrix → {out / f'{key}_confusion_matrix.html'}")

    pr_fig = res.plot_pr_curves()  # type: ignore[attr-defined]
    pr_fig.write_html(str(out / f"{key}_pr_curves.html"))
    logger.info(f"Saved PR curves → {out / f'{key}_pr_curves.html'}")


def _build_sample_lookup(
    version_view: fo.DatasetView,
    images_info: dict[int, dict],
    images_dir: str,
) -> tuple[list[str], dict[int, str], dict[int, tuple[int, int]]]:
    """Match annotation image IDs to FiftyOne samples via filepath.

    Resolves each annotation's ``file_name`` relative to *images_dir* and
    matches it against the absolute ``filepath`` stored on each FiftyOne
    sample.  This is collision-free even when multiple COCO exports assigned
    overlapping sequential ``image_id`` values.

    Returns:
        sample_ids: ordered list of sample IDs in the view.
        id_to_sample: annotation image_id → sample ID.
        id_to_meta: annotation image_id → (width, height).
    """
    logger.info("Building filepath-based sample lookup...")
    filepaths, sample_ids, meta_widths, meta_heights = (
        version_view.values("filepath"),
        version_view.values("id"),
        version_view.values("metadata.width"),
        version_view.values("metadata.height"),
    )

    # filepath → (sample_id, width, height)
    # FiftyOne stores absolute paths built via os.path.join, already normalised.
    fp_lookup: dict[str, tuple[str, int, int]] = {
        fp: (sid, w, h)
        for fp, sid, w, h in zip(filepaths, sample_ids, meta_widths, meta_heights, strict=True)
    }

    # annotation image_id → sample via file_name
    # PurePosixPath avoids filesystem access; compute base once outside the loop.
    base = PurePosixPath(images_dir)
    id_to_sample: dict[int, str] = {}
    id_to_meta: dict[int, tuple[int, int]] = {}
    for image_id, info in images_info.items():
        full_path = str(base / info["file_name"])
        entry = fp_lookup.get(full_path)
        if entry is not None:
            sid, w, h = entry
            id_to_sample[image_id] = sid
            id_to_meta[image_id] = (w, h)

    logger.info(f"Lookup built for {len(id_to_sample)} / {len(images_info)} annotation images")
    return sample_ids, id_to_sample, id_to_meta


def _build_detections(
    preds_by_image: dict[int, list],
    id_to_sample: dict[int, str],
    images_info: dict[int, dict],
    id_to_meta: dict[int, tuple[int, int]],
    categories: dict[int, str],
) -> tuple[dict[str, fo.Detections], set[int]]:
    """Convert COCO predictions to FiftyOne Detections grouped by sample ID.

    Returns:
        sample_detections: sample_id → fo.Detections.
        unmatched_ids: image_ids with no matching sample.
    """
    sample_detections: dict[str, fo.Detections] = {}
    unmatched_ids: set[int] = set()

    logger.info("Building detections in memory...")
    for image_id, preds in tqdm(preds_by_image.items(), desc="Processing images"):
        sample_id = id_to_sample.get(image_id)
        if sample_id is None:
            unmatched_ids.add(image_id)
            continue

        # Resolve image dimensions: prefer annotations, fall back to dataset metadata
        img_info = images_info.get(image_id, {})
        img_w = img_info.get("width") or id_to_meta.get(image_id, (None, None))[0]
        img_h = img_info.get("height") or id_to_meta.get(image_id, (None, None))[1]

        detections = [
            fo.Detection(
                label=categories.get(p["category_id"], "unknown"),
                bounding_box=[
                    p["bbox"][0] / img_w,
                    p["bbox"][1] / img_h,
                    p["bbox"][2] / img_w,
                    p["bbox"][3] / img_h,
                ],
                confidence=float(p["score"]),
            )
            for p in preds
        ]
        sample_detections[sample_id] = fo.Detections(detections=detections)

    logger.info(
        f"Done: {len(sample_detections)} images with predictions, "
        f"{len(unmatched_ids)} image_ids not found in dataset"
    )
    if unmatched_ids:
        logger.warning(f"Unmatched image_ids: {sorted(unmatched_ids)}")
    return sample_detections, unmatched_ids


def _run_evaluation(
    version_view: fo.DatasetView,
    label_field: str,
    gt_field: str,
    eval_key: str,
    iou: float | None,
    report_dir: Path | None,
) -> None:
    """Run a COCO evaluation pass and optionally save results."""
    logger.info(
        f"Evaluating '{label_field}' vs '{gt_field}' (eval_key='{eval_key}', method='coco')..."
    )

    iou_kwargs = {"iou": iou} if iou is not None else {}
    results = version_view.evaluate_detections(
        label_field,
        gt_field=gt_field,
        eval_key=eval_key,
        method="coco",
        classwise=True,
        compute_mAP=True,
        **iou_kwargs,
    )
    results.print_report()
    results.print_metrics()
    if hasattr(results, "mAP"):
        logger.info(f"mAP: {results.mAP():.4f}")
    if report_dir is not None:
        _save_results(results, eval_key, report_dir)
    logger.info(f"Per-sample fields written: '{eval_key}_tp', '{eval_key}_fp', '{eval_key}_fn'")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for prediction loading."""
    parser = argparse.ArgumentParser(
        description="Load COCO-format predictions into an existing FiftyOne dataset"
    )
    parser.add_argument(
        "--dataset-name",
        required=True,
        help="Name of the existing FiftyOne dataset",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Dataset version — predictions are attached only to samples with this version",
    )
    parser.add_argument(
        "--predictions-path",
        required=True,
        help="Path to the COCO results JSON (*.bbox.json)",
    )
    parser.add_argument(
        "--annotations-path",
        required=True,
        help="Path to the COCO annotations JSON (needed for category_id → class name mapping)",
    )
    parser.add_argument(
        "--label-field",
        default="predictions",
        help="FiftyOne field name for the predictions (default: predictions)",
    )
    parser.add_argument(
        "--images-dir",
        required=True,
        help="Root directory for images (used to resolve annotation file_name - FiftyOne filepath)",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Launch the FiftyOne app after loading",
    )
    parser.add_argument(
        "--evaluate",
        action="store_true",
        help="Run evaluate_detections against the ground-truth field after loading",
    )
    parser.add_argument(
        "--gt-field",
        default="ground_truth",
        help="FiftyOne field name for ground-truth labels (default: ground_truth)",
    )
    parser.add_argument(
        "--report-dir",
        default=None,
        help="Directory to save evaluation outputs: JSON report and confusion matrix HTML",
    )
    parser.add_argument(
        "--iou",
        type=float,
        default=None,
        help="IoU threshold for evaluation (default: COCO standard 0.50:0.05:0.95)",
    )
    parser.add_argument(
        "--include-labels",
        nargs="*",
        default=None,
        help="Keep only samples matching KEY=VALUE classification labels (e.g. split=train)",
    )
    return parser.parse_args()


def load_predictions(
    dataset_name: str,
    predictions_path: str,
    annotations_path: str,
    version: str,
    images_dir: str,
    label_field: str = "predictions",
    open_browser: bool = False,
    evaluate: bool = False,
    gt_field: str = "ground_truth",
    report_dir: str | None = None,
    iou: float | None = None,
    include_labels: list[str] | None = None,
) -> fo.Dataset:
    """Load COCO-format predictions into an existing FiftyOne dataset.

    Args:
        dataset_name: Name of the existing FiftyOne dataset.
        predictions_path: Path to the COCO results JSON.
        annotations_path: Path to the COCO annotations JSON.
        version: Only attach predictions to samples with this version.
        images_dir: Root directory for images (resolves annotation file_name - FiftyOne filepath).
        label_field: FiftyOne field name for the predictions.
        include_labels: KEY=VALUE classification filters to narrow the view (e.g. ["split=train"]).
        open_browser: Launch the FiftyOne app after loading.
        evaluate: Run evaluate_detections after loading predictions.
        gt_field: FiftyOne field name for ground-truth labels.
        report_dir: Directory to save the JSON report and confusion matrix HTML.
        iou: IoU threshold for evaluation. None uses COCO defaults (0.50:0.05:0.95).

    Returns:
        The updated FiftyOne dataset.
    """
    dataset, version_view = get_version_view(dataset_name, version)
    parsed_labels = parse_label_filters(include_labels)
    if parsed_labels:
        version_view = apply_label_filters(version_view, include_labels=parsed_labels)
        logger.info(f"Applied label filters: {parsed_labels}")
    version_count = version_view.count()
    if version_count == 0:
        raise ValueError(f"No samples with version '{version}' in dataset '{dataset_name}'")
    logger.info(f"Filtered to {version_count} samples with version '{version}'")

    categories, images_info, preds_by_image = load_coco_metadata(annotations_path, predictions_path)

    sample_ids, id_to_sample, id_to_meta = _build_sample_lookup(
        version_view, images_info, images_dir
    )
    sample_detections, _ = _build_detections(
        preds_by_image, id_to_sample, images_info, id_to_meta, categories
    )

    logger.info(f"Bulk-writing detections for {len(sample_detections)} samples...")
    ordered_detections = [sample_detections.get(sid) for sid in sample_ids]
    version_view.set_values(label_field, ordered_detections)

    if evaluate:
        if not dataset.has_field(gt_field):
            logger.warning(
                f"Ground-truth field '{gt_field}' not found on dataset — skipping evaluation"
            )
        else:
            out = Path(report_dir) if report_dir is not None else None
            if out is not None:
                out.mkdir(parents=True, exist_ok=True)

            _run_evaluation(version_view, label_field, gt_field, label_field, iou, out)

    if open_browser:
        launch_fiftyone_app(dataset, view=dataset.view())

    return dataset


def main() -> None:
    configure_fiftyone()
    args = _parse_args()
    load_predictions(
        dataset_name=args.dataset_name,
        predictions_path=args.predictions_path,
        annotations_path=args.annotations_path,
        version=args.version,
        images_dir=args.images_dir,
        label_field=args.label_field,
        open_browser=args.open_browser,
        evaluate=args.evaluate,
        gt_field=args.gt_field,
        report_dir=args.report_dir,
        iou=args.iou,
        include_labels=args.include_labels,
    )


if __name__ == "__main__":
    main()
