"""Plotting and analysis utilities for detection degradation evaluation."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from src.ood.common.transforms import CORRUPTIONS, SEVERITIES


def load_results(
    results_json: Path,
) -> tuple[float, np.ndarray, float, np.ndarray]:
    """Load a degradation-results JSON and return clean metrics and matrices.

    Each matrix has shape ``(n_corruptions, n_severities)`` with values in
    ``[0, 1]`` representing the ratio of corrupted metric to the clean
    baseline.

    Args:
        results_json: Path to ``detection_degradation_results.json``.

    Returns:
        A 4-tuple ``(clean_mAP, mAP_data, clean_f1, f1_data)`` where each
        data array has shape ``(len(CORRUPTIONS), 5)``.
    """
    with open(results_json, encoding="utf-8") as f:
        raw = json.load(f)
    clean_map: float = raw["clean_mAP"]
    clean_f1: float = raw.get("clean_f1", 0.0)
    map_data = np.zeros((len(CORRUPTIONS), len(SEVERITIES)))
    f1_data = np.zeros((len(CORRUPTIONS), len(SEVERITIES)))
    for i, ctype in enumerate(CORRUPTIONS):
        for j, sev in enumerate(SEVERITIES):
            entry = raw["results"].get(ctype, {}).get(str(sev), {})
            map_data[i, j] = entry.get("relative_mAP", 0.0)
            f1_data[i, j] = entry.get("relative_f1", 0.0)
    return clean_map, map_data, clean_f1, f1_data


def recommend_ood_filter(
    data: np.ndarray,
    threshold: float = 0.80,
) -> str:
    """Derive an ``ood_filter`` string from a relative-mAP matrix.

    For each corruption type the function finds the lowest severity at
    which the relative mAP drops below *threshold*.  If every corruption
    crosses the threshold at the same severity the compact ``"all:<sev>"``
    form is returned; otherwise per-corruption entries are joined.

    Args:
        data: Array of shape ``(n_corruptions, n_severities)`` with
            relative mAP values (1.0 = no degradation).
        threshold: Relative mAP below which a corruption x severity pair
            is considered harmful to detection.

    Returns:
        Filter string for ``dvc_config.yaml``'s ``train.ood_filter``
        (e.g. ``"all:3"`` or ``"fog:2,snow:3,..."``).
    """
    per_corruption: dict[str, int] = {}
    for i, ctype in enumerate(CORRUPTIONS):
        for j, sev in enumerate(SEVERITIES):
            if data[i, j] < threshold:
                per_corruption[ctype] = sev
                break

    if not per_corruption:
        return "all:5"

    min_sev = min(per_corruption.values())
    if all(v == min_sev for v in per_corruption.values()):
        return f"all:{min_sev}"
    return ",".join(f"{c}:{s}" for c, s in sorted(per_corruption.items()))


def _plot_bar(
    data: np.ndarray,
    *,
    threshold: float,
    ylabel: str,
    title: str,
    output_path: Path,
) -> None:
    """Generate a bar chart of mean relative metric per severity.

    Args:
        data: Array of shape ``(n_corruptions, n_severities)``.
        threshold: Horizontal line threshold value.
        ylabel: Y-axis label.
        title: Chart title.
        output_path: Destination file path for the saved figure.
    """
    mean_per_sev = data.mean(axis=0)
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar(SEVERITIES, mean_per_sev, color="steelblue")
    ax.axhline(
        threshold,
        ls="--",
        color="red",
        label=f"{1 - threshold:.0%} degradation threshold",
    )
    ax.set_xlabel("Corruption severity")
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.set_ylim(0, 1.05)
    ax.legend()
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def _plot_heatmap(
    data: np.ndarray,
    *,
    metric_label: str,
    title: str,
    output_path: Path,
) -> None:
    """Generate a heatmap of relative metric per corruption x severity.

    Args:
        data: Array of shape ``(n_corruptions, n_severities)``.
        metric_label: Colorbar label (e.g. ``"Relative mAP"``).
        title: Chart title.
        output_path: Destination file path for the saved figure.
    """
    fig, ax = plt.subplots(figsize=(8, 5))
    im = ax.imshow(data, aspect="auto", vmin=0, vmax=1, cmap="RdYlGn")
    ax.set_xticks(range(len(SEVERITIES)))
    ax.set_xticklabels(SEVERITIES)
    ax.set_yticks(range(len(CORRUPTIONS)))
    ax.set_yticklabels(CORRUPTIONS)
    ax.set_xlabel("Severity")
    ax.set_ylabel("Corruption type")
    ax.set_title(title)
    for i in range(len(CORRUPTIONS)):
        for j in range(len(SEVERITIES)):
            ax.text(
                j,
                i,
                f"{data[i, j]:.2f}",
                ha="center",
                va="center",
                fontsize=8,
            )
    fig.colorbar(im, label=metric_label)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def plot_degradation(
    results_json: Path,
    output_dir: Path,
    threshold: float = 0.80,
) -> str:
    """Generate detection-degradation plots and the recommended OOD filter.

    Produces:

    * ``detection_degradation_bar.png`` — mean relative mAP per severity.
    * ``detection_degradation_heatmap.png`` — per corruption x severity mAP.
    * ``detection_degradation_f1_bar.png`` — mean relative F1 per severity.
    * ``detection_degradation_f1_heatmap.png`` — per corruption x severity F1.
    * ``recommended_ood_filter.txt`` — single-line filter string.

    The OOD filter recommendation is based on the mAP threshold only.

    Args:
        results_json: Path to ``detection_degradation_results.json``
            produced by the evaluation script.
        output_dir: Directory where plots and the filter file are saved.
            Created if it does not exist.
        threshold: Relative mAP below which a corruption x severity pair
            is considered harmful to detection.

    Returns:
        The recommended ``ood_filter`` string.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    clean_map, map_data, clean_f1, f1_data = load_results(results_json)

    # mAP plots
    _plot_bar(
        map_data,
        threshold=threshold,
        ylabel="Relative mAP (corrupted / clean)",
        title="Detection performance vs corruption severity",
        output_path=output_dir / "detection_degradation_bar.png",
    )
    _plot_heatmap(
        map_data,
        metric_label="Relative mAP",
        title=f"Detection mAP per corruption x severity (clean={clean_map:.3f})",
        output_path=output_dir / "detection_degradation_heatmap.png",
    )

    # F1 plots
    _plot_bar(
        f1_data,
        threshold=threshold,
        ylabel="Relative F1 (corrupted / clean)",
        title="Detection F1 vs corruption severity",
        output_path=output_dir / "detection_degradation_f1_bar.png",
    )
    _plot_heatmap(
        f1_data,
        metric_label="Relative F1",
        title=f"Detection F1 per corruption x severity (clean={clean_f1:.3f})",
        output_path=output_dir / "detection_degradation_f1_heatmap.png",
    )

    # Recommend ood_filter (based on mAP)
    rec = recommend_ood_filter(map_data, threshold=threshold)
    (output_dir / "recommended_ood_filter.txt").write_text(rec + "\n")
    return rec
