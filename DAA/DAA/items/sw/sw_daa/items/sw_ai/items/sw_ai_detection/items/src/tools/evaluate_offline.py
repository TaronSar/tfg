from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import matplotlib
import numpy as np
import pandas as pd
from loguru import logger
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.container import BarContainer
from pycocotools.coco import COCO
from pycocotools.cocoeval import COCOeval

matplotlib.use("Agg")
import matplotlib.pyplot as plt

_BREAKDOWN_METRICS = ["mAP", "mAP_50", "mAP_75", "AR@100"]


def _load_gt(path: str) -> tuple[dict, COCO]:
    """Load a COCO ground-truth JSON file.

    Args:
        path: Path to the COCO JSON file.

    Returns:
        Tuple of:
        - The raw ground-truth dict.
        - A ``COCO`` object with the index built.
    """
    with open(path) as f:
        gt_dict = json.load(f)
    coco_gt = COCO()
    coco_gt.dataset = gt_dict
    coco_gt.createIndex()
    return gt_dict, coco_gt


def _load_predictions(
    path: str, score_thr: float, valid_img_ids: set[int] | None = None
) -> list[dict]:
    """Load predictions from a COCO results JSON file.

    Args:
        path: Path to the predictions JSON (standard COCO bbox results format).
        score_thr: Predictions with score below this threshold are discarded.
            Pass ``0.0`` to keep all predictions.
        valid_img_ids: If provided, predictions whose ``image_id`` is not in
            this set are dropped.

    Returns:
        List of prediction dicts after score and image-id filtering.
    """
    with open(path) as f:
        preds = json.load(f)
    if score_thr > 0:
        preds = [p for p in preds if p["score"] >= score_thr]
    if valid_img_ids is not None:
        n_before = len(preds)
        preds = [p for p in preds if p["image_id"] in valid_img_ids]
        n_dropped = n_before - len(preds)
        if n_dropped:
            logger.info(f"  Dropped {n_dropped} predictions with image_ids not in GT.")
    return preds


def _run_coco_eval(
    coco_gt: COCO,
    predictions: list[dict],
    area_rng: list[list[float]] | None = None,
    area_rng_lbl: list[str] | None = None,
    max_dets: list[int] | None = None,
    per_class: bool = False,
) -> dict[str, float]:
    """Run COCOeval and return a flat metrics dict.

    Args:
        coco_gt: Ground-truth ``COCO`` object.
        predictions: List of prediction dicts in COCO results format.
        area_rng: Custom area ranges as ``[[lo, hi], ...]``.
            Defaults to the COCOeval default ranges.
        area_rng_lbl: Labels for each area range.
            Must match the length of ``area_rng``.
        max_dets: Maximum detections per image for AR computation
            (e.g. ``[1, 10, 100]``).
        per_class: If ``True``, include per-class AP and AP@50 in the
            returned dict under keys ``AP_<name>`` and ``AP_50_<name>``.

    Returns:
        Flat dict mapping metric name → score.  Returns an empty dict if
        ``predictions`` is empty.
    """
    if not predictions:
        return {}

    coco_dt = coco_gt.loadRes(predictions)
    coco_eval = COCOeval(coco_gt, coco_dt, "bbox")

    if area_rng is not None:
        coco_eval.params.areaRng = area_rng
        coco_eval.params.areaRngLbl = area_rng_lbl or [f"area_{i}" for i in range(len(area_rng))]
    if max_dets is not None:
        coco_eval.params.maxDets = max_dets

    coco_eval.evaluate()
    coco_eval.accumulate()
    coco_eval.summarize()

    stats = coco_eval.stats
    labels = area_rng_lbl or coco_eval.params.areaRngLbl
    m_dets = max_dets or coco_eval.params.maxDets

    metrics: dict[str, float] = {
        "mAP": float(stats[0]),
        "mAP_50": float(stats[1]),
        "mAP_75": float(stats[2]),
        f"mAP_{labels[1]}": float(stats[3]),
        f"mAP_{labels[2]}": float(stats[4]),
        f"mAP_{labels[3]}": float(stats[5]),
        f"AR@{m_dets[0]}": float(stats[6]),
        f"AR@{m_dets[1]}": float(stats[7]),
        f"AR@{m_dets[2]}": float(stats[8]),
        f"AR_{labels[1]}@{m_dets[2]}": float(stats[9]),
        f"AR_{labels[2]}@{m_dets[2]}": float(stats[10]),
        f"AR_{labels[3]}@{m_dets[2]}": float(stats[11]),
    }

    if per_class:
        cat_ids = coco_gt.getCatIds()
        cat_names = {c["id"]: c["name"] for c in coco_gt.loadCats(cat_ids)}
        # precision shape: [T, R, K, A, M] – iou x recall x cat x area x maxDet
        precision = coco_eval.eval["precision"]  # (10, 101, K, 4, 3)
        for k_idx, cat_id in enumerate(coco_eval.params.catIds):
            name = cat_names.get(cat_id, str(cat_id))
            # AP across all IoU thresholds, all area ranges, maxDet[-1]
            ap = precision[:, :, k_idx, 0, -1]
            ap_valid = ap[ap > -1]
            if len(ap_valid):
                metrics[f"AP_{name}"] = float(np.mean(ap_valid))
            else:
                metrics[f"AP_{name}"] = float("nan")

            ap50 = precision[0, :, k_idx, 0, -1]
            ap50_valid = ap50[ap50 > -1]
            if len(ap50_valid):
                metrics[f"AP_50_{name}"] = float(np.mean(ap50_valid))
            else:
                metrics[f"AP_50_{name}"] = float("nan")

    return metrics


def _make_bins(edges: list[float]) -> list[tuple[float, float]]:
    """Turn a list of edges into half-open intervals.

    Example: ``[0, 500, 1000]`` → ``[(0, 500), (500, 1000)]``.

    Args:
        edges: Monotonically increasing list of bin boundary values.
            Must contain at least two values.

    Returns:
        List of ``(lo, hi)`` half-open intervals ``[lo, hi)``.

    Raises:
        ValueError: If fewer than two edges are provided.
    """
    if len(edges) < 2:
        raise ValueError(f"At least two edges are required to form bins, got {len(edges)}.")
    return [(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def _filter_gt_and_preds_by_ann_ids(
    gt_dict: dict,
    predictions: list[dict],
    keep_ann_ids: set[int],
) -> tuple[COCO, list[dict]]:
    """Build a filtered COCO GT restricted to the given annotation IDs.

    Annotations NOT in ``keep_ann_ids`` but sharing an image with a kept
    annotation are re-inserted as ``iscrowd=1`` (ignored) so that predictions
    matched to them are treated as neither TP nor FP by COCOeval.  Without
    this, those predictions would be unmatched false positives and would
    artificially deflate precision for the slice.

    Predictions are filtered to only those whose ``image_id`` appears in
    the filtered ground truth.

    Args:
        gt_dict: Raw ground-truth COCO dict.
        predictions: Full list of prediction dicts.
        keep_ann_ids: Annotation IDs to retain as active (scored) GT.

    Returns:
        Tuple of:
        - Filtered ``COCO`` object.
        - Predictions restricted to images present in the filtered GT.
    """
    active_anns = [a for a in gt_dict["annotations"] if a["id"] in keep_ann_ids]
    keep_img_ids = {a["image_id"] for a in active_anns}

    ignored_anns = [
        {**a, "iscrowd": 1}
        for a in gt_dict["annotations"]
        if a["id"] not in keep_ann_ids and a["image_id"] in keep_img_ids
    ]

    filtered_gt = {k: v for k, v in gt_dict.items() if k not in ("annotations", "images")}
    filtered_gt["annotations"] = active_anns + ignored_anns
    filtered_gt["images"] = [i for i in gt_dict["images"] if i["id"] in keep_img_ids]

    coco_filtered = COCO()
    coco_filtered.dataset = filtered_gt
    coco_filtered.createIndex()

    filtered_preds = [p for p in predictions if p["image_id"] in keep_img_ids]
    return coco_filtered, filtered_preds


def _eval_by_range(
    gt_dict: dict,
    predictions: list[dict],
    bins: list[tuple[float, float]],
    per_class: bool,
) -> dict[str, dict]:
    """Evaluate COCO metrics for each range_m bin.

    Annotations without a ``range_m`` attribute or with a negative value are
    collected into an ``"unknown"`` bin.  Annotations exceeding the last bin
    edge are collected into a ``">={max}m"`` overflow bin.

    Args:
        gt_dict: Raw ground-truth COCO dict.
        predictions: List of prediction dicts.
        bins: List of ``(lo, hi)`` half-open range intervals in metres.
        per_class: Whether to include per-class AP in each bin's metrics.

    Returns:
        Dict mapping bin label → metrics dict (same format as
        :func:`_run_coco_eval`).
    """
    ann_by_bin: dict[str, set[int]] = defaultdict(set)
    for ann in gt_dict["annotations"]:
        r = ann.get("range_m")
        if r is None or r < 0:
            ann_by_bin["unknown"].add(ann["id"])
            continue
        for lo, hi in bins:
            if lo <= r < hi:
                ann_by_bin[f"{lo:.0f}-{hi:.0f}m"].add(ann["id"])
                break
        else:
            ann_by_bin[f">={bins[-1][1]:.0f}m"].add(ann["id"])

    results: dict[str, dict] = {}
    for label, ann_ids in sorted(ann_by_bin.items(), key=lambda x: _bin_sort_key(x[0])):
        logger.info("=" * 60)
        logger.info(f"Range bin: {label}  ({len(ann_ids)} annotations)")
        logger.info("=" * 60)
        coco_f, preds_f = _filter_gt_and_preds_by_ann_ids(gt_dict, predictions, ann_ids)
        results[label] = _run_coco_eval(coco_f, preds_f, per_class=per_class)
    return results


def _eval_by_geometry(
    gt_dict: dict,
    predictions: list[dict],
    bins: list[tuple[float, float]],
    dimension: str,
    per_class: bool,
) -> dict[str, dict]:
    """Evaluate COCO metrics for each bbox geometry bin.

    Annotations whose value exceeds the last bin edge are collected into a
    ``">={max}"`` overflow bin.

    Args:
        gt_dict: Raw ground-truth COCO dict.
        predictions: List of prediction dicts.
        bins: List of ``(lo, hi)`` half-open intervals.
        dimension: Bbox attribute to slice by.  One of ``"area"``,
            ``"width"``, or ``"height"``.
        per_class: Whether to include per-class AP in each bin's metrics.

    Returns:
        Dict mapping bin label → metrics dict (same format as
        :func:`_run_coco_eval`).

    Raises:
        ValueError: If ``dimension`` is not one of the supported values.
    """
    ann_by_bin: dict[str, set[int]] = defaultdict(set)
    for ann in gt_dict["annotations"]:
        bbox = ann["bbox"]  # [x, y, w, h]
        w, h = bbox[2], bbox[3]
        if dimension == "area":
            val = w * h
        elif dimension == "width":
            val = w
        elif dimension == "height":
            val = h
        else:
            raise ValueError(
                f"Unknown dimension '{dimension}'. Must be one of 'area', 'width', 'height'."
            )

        for lo, hi in bins:
            if lo <= val < hi:
                ann_by_bin[f"{lo:.0f}-{hi:.0f}"].add(ann["id"])
                break
        else:
            ann_by_bin[f">={bins[-1][1]:.0f}"].add(ann["id"])

    results: dict[str, dict] = {}
    for label, ann_ids in sorted(ann_by_bin.items(), key=lambda x: _bin_sort_key(x[0])):
        logger.info("=" * 60)
        logger.info(f"{dimension.capitalize()} bin: {label}  ({len(ann_ids)} annotations)")
        logger.info("=" * 60)
        coco_f, preds_f = _filter_gt_and_preds_by_ann_ids(gt_dict, predictions, ann_ids)
        results[label] = _run_coco_eval(coco_f, preds_f, per_class=per_class)
    return results


def _print_summary_table(
    section_name: str,
    results: dict[str, dict[str, float]],
) -> None:
    """Print a compact summary table for a breakdown section.

    Args:
        section_name: Human-readable name of the breakdown section
            (used as the table title).
        results: Dict mapping bin label → metrics dict.
    """
    if not results:
        return
    key_metrics = _BREAKDOWN_METRICS
    logger.info(f"\n{'─' * 70}")
    logger.info(f"  Summary: {section_name}")
    logger.info(f"{'─' * 70}")
    header = f"  {'Bin':<20s}" + "".join(f"{k:>10s}" for k in key_metrics)
    logger.info(header)
    logger.info(f"  {'─' * 20}" + "─" * (10 * len(key_metrics)))
    for bin_label, metrics in results.items():
        row = f"  {bin_label:<20s}"
        for k in key_metrics:
            v = metrics.get(k, float("nan"))
            row += f"{v:>10.3f}" if not np.isnan(v) else f"{'N/A':>10s}"
        logger.info(row)
    logger.info("" + "─" * 70)


def _bin_sort_key(label: str) -> float:
    """Extract the leading number from a bin label for numeric sorting.

    Args:
        label: Bin label string such as ``"0-500m"`` or ``">=1000"``.

    Returns:
        The first numeric value found in the label, or ``inf`` if none.
    """
    m = re.search(r"[\d.]+", label)
    return float(m.group()) if m else float("inf")


def _section_to_dataframe(
    section: dict[str, dict[str, float]],
) -> pd.DataFrame:
    """Convert a breakdown section to a sorted DataFrame.

    Args:
        section: Dict mapping bin label → metrics dict.

    Returns:
        DataFrame indexed by bin label, rows sorted numerically by the
        leading number in each label.  Pycocotools sentinel value ``-1.0``
        is replaced by ``NaN``.
    """
    df = pd.DataFrame.from_dict(section, orient="index")
    df.index.name = "bin"
    # Sort rows by the leading number in each bin label (numeric, not lexicographic)
    df = df.iloc[sorted(range(len(df)), key=lambda i: _bin_sort_key(df.index[i]))]
    # Replace pycocotools -1 (no GT in that area range) with NaN
    df = df.replace(-1.0, np.nan)
    return df


def _plot_breakdown_bars(
    df: pd.DataFrame,
    title: str,
    metrics: list[str] | None = None,
    ax: plt.Axes | None = None,
) -> plt.Axes | None:
    """Render a grouped bar chart for a breakdown DataFrame.

    Args:
        df: DataFrame indexed by bin label with metric columns.
        title: Chart title.
        metrics: Metric column names to include.  Defaults to
            :data:`_BREAKDOWN_METRICS`.
        ax: Existing :class:`~matplotlib.axes.Axes` to draw into.
            A new figure is created when ``None``.

    Returns:
        The axes containing the chart.
    """
    metrics = metrics or _BREAKDOWN_METRICS
    cols = [c for c in metrics if c in df.columns]
    if not cols:
        return ax
    plot_df = df[cols].copy()
    if ax is None:
        _, ax = plt.subplots(figsize=(max(6, len(plot_df) * 1.4), 4.5))
    plot_df.plot.bar(ax=ax, width=0.75, edgecolor="white", linewidth=0.5)
    ax.set_title(title, fontsize=12, fontweight="bold")
    ax.set_ylabel("Score")
    ax.set_xlabel("")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8, ncol=len(cols), loc="upper right")
    ax.tick_params(axis="x", rotation=30)
    # value labels on top of bars
    for container in ax.containers:
        if isinstance(container, BarContainer):
            ax.bar_label(container, fmt="%.2f", fontsize=6, padding=1)
    ax.grid(axis="y", alpha=0.3)
    return ax


def _plot_per_class_ap(
    overall: dict[str, float],
    ax: plt.Axes | None = None,
) -> plt.Axes | None:
    """Render a horizontal bar chart of per-class AP and AP@50.

    Args:
        overall: Overall metrics dict containing ``AP_<name>`` and
            ``AP_50_<name>`` entries.
        ax: Existing :class:`~matplotlib.axes.Axes` to draw into.
            A new figure is created when ``None``.

    Returns:
        The axes containing the chart, or ``None`` if no per-class AP
        data is present or all values are ``NaN``.
    """
    ap_keys = {
        k: k.removeprefix("AP_")
        for k in overall
        if k.startswith("AP_") and not k.startswith("AP_50_")
    }
    if not ap_keys:
        return None
    names = list(ap_keys.values())
    ap_vals = [overall[k] for k in ap_keys]
    ap50_vals = [overall.get(f"AP_50_{n}", np.nan) for n in names]

    # filter out classes that are all NaN
    valid = [
        (n, a, a50)
        for n, a, a50 in zip(names, ap_vals, ap50_vals, strict=True)
        if not (np.isnan(a) and np.isnan(a50))
    ]
    if not valid:
        return None
    names_z, ap_vals_z, ap50_vals_z = zip(*valid, strict=True)
    names = list(names_z)
    ap_vals = list(ap_vals_z)
    ap50_vals = list(ap50_vals_z)

    if ax is None:
        _, ax = plt.subplots(figsize=(7, max(3, len(names) * 0.5 + 1)))
    y = np.arange(len(names))
    h = 0.35
    bars1 = ax.barh(y - h / 2, ap_vals, h, label="AP", color="#4c72b0")
    bars2 = ax.barh(y + h / 2, ap50_vals, h, label="AP@50", color="#55a868")
    ax.set_yticks(y)
    ax.set_yticklabels(names)
    ax.set_xlim(0, 1.05)
    ax.set_xlabel("Score")
    ax.set_title("Per-class AP", fontsize=12, fontweight="bold")
    ax.legend(fontsize=8)
    ax.bar_label(bars1, fmt="%.2f", fontsize=7, padding=2)
    ax.bar_label(bars2, fmt="%.2f", fontsize=7, padding=2)
    ax.grid(axis="x", alpha=0.3)
    return ax


def _plot_overall_summary(
    overall: dict[str, float],
    ax: plt.Axes | None = None,
) -> plt.Axes | None:
    """Render a bar chart of overall COCO metrics.

    Args:
        overall: Overall metrics dict (output of :func:`_run_coco_eval`).
        ax: Existing :class:`~matplotlib.axes.Axes` to draw into.
            A new figure is created when ``None``.

    Returns:
        The axes containing the chart.
    """
    keys = [
        "mAP",
        "mAP_50",
        "mAP_75",
        "mAP_small",
        "mAP_medium",
        "mAP_large",
        "AR@1",
        "AR@10",
        "AR@100",
    ]
    present = [(k, overall[k]) for k in keys if k in overall and overall[k] != -1.0]
    if not present:
        return ax
    labels, values = zip(*present, strict=True)
    if ax is None:
        _, ax = plt.subplots(figsize=(max(6, len(labels) * 0.8), 4))
    colors = ["#4c72b0" if "mAP" in lbl else "#dd8452" for lbl in labels]
    bars = ax.bar(labels, values, color=colors, edgecolor="white", linewidth=0.5)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Score")
    ax.set_title("Overall COCO Metrics", fontsize=12, fontweight="bold")
    ax.bar_label(bars, fmt="%.3f", fontsize=7, padding=2)
    ax.tick_params(axis="x", rotation=35)
    ax.grid(axis="y", alpha=0.3)
    return ax


def generate_report(all_results: dict[str, Any], report_dir: str | Path) -> Path:
    """Generate a plots report from evaluation results.

    Creates a directory with individual PNG plots and a combined
    ``report.png`` summary figure.  Also writes ``summary.csv``
    tables for each breakdown section.

    Args:
        all_results: Dict returned by :func:`main` containing evaluation
            results for each section.
        report_dir: Directory path where all report files will be written.
            Created if it does not exist.

    Returns:
        Resolved path to the report directory.
    """
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)

    figures: list[tuple[str, plt.Figure]] = []
    overall = all_results.get("overall", {})

    if overall:
        fig, ax = plt.subplots(figsize=(9, 4))
        _plot_overall_summary(overall, ax=ax)
        fig.tight_layout()
        fig.savefig(report_dir / "overall_metrics.png", dpi=150)
        figures.append(("Overall COCO Metrics", fig))

    if overall:
        fig_pc, ax_pc = plt.subplots(figsize=(7, 4))
        ret = _plot_per_class_ap(overall, ax=ax_pc)
        if ret is not None:
            fig_pc.tight_layout()
            fig_pc.savefig(report_dir / "per_class_ap.png", dpi=150)
            figures.append(("Per-class AP", fig_pc))
        else:
            plt.close(fig_pc)

    section_labels = {
        "by_range_m": "Metrics by Range (m)",
        "by_area": "Metrics by BBox Area (px²)",
        "by_width": "Metrics by BBox Width (px)",
        "by_height": "Metrics by BBox Height (px)",
    }
    for key, title in section_labels.items():
        section = all_results.get(key)
        if not section:
            continue
        df = _section_to_dataframe(section)
        # Save CSV
        csv_path = report_dir / f"{key}.csv"
        df.to_csv(csv_path, float_format="%.4f")

        # Bar chart
        fig, ax = plt.subplots(figsize=(max(6, len(df) * 1.4), 4.5))
        _plot_breakdown_bars(df, title, ax=ax)
        fig.tight_layout()
        fig.savefig(report_dir / f"{key}.png", dpi=150)
        figures.append((title, fig))

        # Per-class breakdown (if available)
        ap_cols = [c for c in df.columns if c.startswith("AP_") and not c.startswith("AP_50_")]
        if ap_cols:
            fig2, ax2 = plt.subplots(figsize=(max(6, len(df) * 1.4), 4.5))
            _plot_breakdown_bars(df, f"{title} – Per-class AP", metrics=ap_cols, ax=ax2)
            fig2.tight_layout()
            fig2.savefig(report_dir / f"{key}_per_class.png", dpi=150)
            figures.append((f"{title} – Per-class", fig2))

    if figures:
        n = len(figures)
        combined, axes = plt.subplots(n, 1, figsize=(12, 4.5 * n))
        if n == 1:
            axes = [axes]
        for (_title, src_fig), ax in zip(figures, axes, strict=True):
            src_fig.canvas.draw()
            canvas = src_fig.canvas
            if not isinstance(canvas, FigureCanvasAgg):
                raise RuntimeError(
                    f"Expected FigureCanvasAgg (matplotlib Agg backend), "
                    f"got {type(canvas).__name__}. "
                    "Ensure matplotlib.use('Agg') is called before importing pyplot."
                )
            img = np.frombuffer(canvas.buffer_rgba(), dtype=np.uint8)
            img = img.reshape(canvas.get_width_height()[::-1] + (4,))
            ax.imshow(img)
            ax.set_axis_off()
        combined.tight_layout()
        combined.savefig(report_dir / "report.png", dpi=150)
        plt.close(combined)

    for _, fig in figures:
        plt.close(fig)

    if overall:
        overall_clean = {k: v for k, v in overall.items() if v != -1.0}
        pd.Series(overall_clean, name="value").to_csv(
            report_dir / "overall.csv",
            float_format="%.4f",
            header=True,
        )

    logger.info(f"\nReport saved to {report_dir}/")
    return report_dir


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for offline COCO evaluation.

    Returns:
        Parsed arguments namespace.
    """
    p = argparse.ArgumentParser(
        description="Offline COCO evaluation with range / geometry breakdowns.",
    )
    p.add_argument("--gt", required=True, help="Path to COCO ground-truth JSON.")
    p.add_argument("--predictions", required=True, help="Path to predictions .bbox.json.")
    p.add_argument(
        "--score-thr",
        type=float,
        default=0.0,
        help="Discard predictions below this score (default: keep all).",
    )
    p.add_argument(
        "--range-bins",
        type=float,
        nargs="+",
        default=None,
        help="Edges for range_m bins, e.g. 0 500 1000 2000 3000.",
    )
    p.add_argument(
        "--area-bins",
        type=float,
        nargs="+",
        default=None,
        help="Edges for bbox area bins (px²), e.g. 0 200 2500 10000.",
    )
    p.add_argument(
        "--width-bins",
        type=float,
        nargs="+",
        default=None,
        help="Edges for bbox width bins (px), e.g. 0 10 30 60.",
    )
    p.add_argument(
        "--height-bins",
        type=float,
        nargs="+",
        default=None,
        help="Edges for bbox height bins (px), e.g. 0 10 30 60.",
    )
    p.add_argument(
        "--per-class",
        action="store_true",
        help="Include per-class AP in each evaluation.",
    )
    p.add_argument(
        "--eval-area-ranges",
        type=float,
        nargs="+",
        default=None,
        metavar="LO HI",
        help=(
            "Flat list of (lo, hi) area-range pairs in px² for the overall COCO eval, "
            "e.g. 0 1e10 0 200 200 2500 2500 1e10. "
            "Must be an even number of values. "
            "Default: 0 1e10 0 200 200 2500 2500 1e10."
        ),
    )
    p.add_argument(
        "--eval-area-labels",
        type=str,
        nargs="+",
        default=None,
        metavar="LABEL",
        help=(
            "Labels for each area range pair (one per pair in --eval-area-ranges). "
            "The first label is the catch-all range. "
            "Default: all small medium large."
        ),
    )
    p.add_argument(
        "--max-dets",
        type=int,
        nargs="+",
        default=None,
        metavar="N",
        help=(
            "Maximum detections per image thresholds for AR computation, "
            "e.g. 1 10 100. Exactly three values are required. "
            "Default: 1 10 100."
        ),
    )
    p.add_argument(
        "--output",
        default=None,
        help="Write all results to a JSON file.",
    )
    p.add_argument(
        "--report-dir",
        default=None,
        help="Directory to write plots report (PNGs + CSVs).",
    )
    return p.parse_args()


def main() -> dict[str, Any]:
    """Entry point for offline COCO evaluation.

    Returns:
        Dict containing all evaluation results keyed by section
        (``"overall"``, ``"by_range_m"``, ``"by_area"``, ``"by_width"``,
        ``"by_height"``).
    """
    args = parse_args()

    logger.info(f"Ground truth : {args.gt}")
    logger.info(f"Predictions  : {args.predictions}")
    logger.info(f"Score thr    : {args.score_thr}")

    gt_dict, coco_gt = _load_gt(args.gt)
    gt_img_ids = {img["id"] for img in gt_dict["images"]}
    predictions = _load_predictions(args.predictions, args.score_thr, gt_img_ids)

    logger.info(f"GT images    : {len(gt_dict['images'])}")
    logger.info(f"GT anns      : {len(gt_dict['annotations'])}")
    logger.info(f"Predictions  : {len(predictions)} (after score filter)")

    all_results: dict[str, Any] = {}

    if args.eval_area_ranges is not None:
        flat = args.eval_area_ranges
        if len(flat) % 2 != 0:
            raise ValueError(
                f"--eval-area-ranges requires an even number of values, got {len(flat)}."
            )
        area_rng: list[list[float]] = [[flat[i], flat[i + 1]] for i in range(0, len(flat), 2)]
    else:
        area_rng = [[0, 1e5**2], [0, 200], [200, 2500], [2500, 1e5**2]]

    area_lbl: list[str] = args.eval_area_labels or ["all", "small", "medium", "large"]

    if len(area_lbl) != len(area_rng):
        raise ValueError(
            f"--eval-area-labels length ({len(area_lbl)}) must match "
            f"the number of area ranges ({len(area_rng)})."
        )

    max_dets: list[int] = args.max_dets or [1, 10, 100]
    if len(max_dets) != 3:
        raise ValueError(
            f"--max-dets requires exactly 3 values (got {len(max_dets)}): "
            "one each for AR@low, AR@mid, AR@high."
        )

    overall = _run_coco_eval(
        coco_gt,
        predictions,
        area_rng=area_rng,
        area_rng_lbl=area_lbl,
        max_dets=max_dets,
        per_class=args.per_class,
    )
    all_results["overall"] = overall

    if args.range_bins:
        bins = _make_bins(args.range_bins)
        logger.info(f"\n\n{'#' * 60}")
        logger.info(f"  Evaluation by range_m  (bins: {bins})")
        logger.info("#" * 60)
        range_results = _eval_by_range(gt_dict, predictions, bins, args.per_class)
        all_results["by_range_m"] = range_results
        _print_summary_table("range_m", range_results)

    if args.area_bins:
        bins = _make_bins(args.area_bins)
        logger.info(f"\n\n{'#' * 60}")
        logger.info(f"  Evaluation by bbox area  (bins: {bins})")
        logger.info("#" * 60)
        area_results = _eval_by_geometry(gt_dict, predictions, bins, "area", args.per_class)
        all_results["by_area"] = area_results
        _print_summary_table("bbox area (px²)", area_results)

    if args.width_bins:
        bins = _make_bins(args.width_bins)
        logger.info(f"\n\n{'#' * 60}")
        logger.info(f"  Evaluation by bbox width  (bins: {bins})")
        logger.info("#" * 60)
        width_results = _eval_by_geometry(gt_dict, predictions, bins, "width", args.per_class)
        all_results["by_width"] = width_results
        _print_summary_table("bbox width (px)", width_results)

    if args.height_bins:
        bins = _make_bins(args.height_bins)
        logger.info(f"\n\n{'#' * 60}")
        logger.info(f"  Evaluation by bbox height  (bins: {bins})")
        logger.info("#" * 60)
        height_results = _eval_by_geometry(gt_dict, predictions, bins, "height", args.per_class)
        all_results["by_height"] = height_results
        _print_summary_table("bbox height (px)", height_results)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w") as f:
            json.dump(all_results, f, indent=2, default=str)
        logger.info(f"\nResults saved to {out_path}")

    if args.report_dir:
        generate_report(all_results, args.report_dir)

    return all_results


if __name__ == "__main__":
    main()
