#!/usr/bin/env python3
"""
Analyze Monte Carlo DAA results.

Reads the CSV produced by ``run_montecarlo.py`` and computes:
  * Confusion matrix (TP / FP / TN / FN) for collision detection
  * Detection rates, false-alarm rates, missed-detection rates
  * Break-downs by encounter geometry (azimuth, offset, speed, …)
  * Optional figures saved to disk

Usage
-----
    python analyze_results.py --input montecarlo_results.csv
    python analyze_results.py --input montecarlo_results.csv --plots --plot-dir figures/
"""

import argparse
import os

import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Imports from sibling packages.
# ---------------------------------------------------------------------------
from daa_conflict_prediction.conflict_prediction import (
    classify_result,
    fn_sub_reason,
    DEFAULT_DEAD_ZONE_S,
    DEFAULT_LEAD_TIME_MARGIN_S,
)

# Optional — only needed for plotting
try:
    import matplotlib
    if __name__ == '__main__':
        matplotlib.use('Agg')  # Non-interactive backend for batch runs
    import matplotlib.pyplot as plt
    _HAS_MPL = True
except ImportError:
    _HAS_MPL = False


# ---------------------------------------------------------------------------
# Confusion matrix helpers — zone-aware classification
# ---------------------------------------------------------------------------


def classify_encounter(
    row: pd.Series,
    dead_zone_s: float = DEFAULT_DEAD_ZONE_S,
    lead_time_margin_s: float = DEFAULT_LEAD_TIME_MARGIN_S,
) -> str:
    """Classify a single encounter result into TP / FP / TN / FN.

    Delegates to :func:`conflict_prediction.classify_result` for the
    core zone-aware logic.
    """
    return classify_result(
        gt_collision=bool(row['gt_collision']),
        detected=bool(row['daa_collision_detected']),
        lead_time_s=row.get('daa_lead_time_s', np.nan),
        lookahead_s=row.get('lookahead_s', np.inf),
        dead_zone_s=dead_zone_s,
        lead_time_margin_s=lead_time_margin_s,
    )


def compute_confusion(
    df: pd.DataFrame,
    dead_zone_s: float = DEFAULT_DEAD_ZONE_S,
    lead_time_margin_s: float = DEFAULT_LEAD_TIME_MARGIN_S,
) -> dict:
    """Compute TP / FP / TN / FN using zone-aware classification.

    An alert is a True Positive only if it fires between *dead_zone_s* and
    the encounter's *lookahead_s + lead_time_margin_s* seconds before actual
    cylinder penetration.  Alerts that fire earlier than that are considered
    unrelated to the real collision (the 1-sigma inflation triggered on a
    different predicted geometry).
    """
    labels = df.apply(
        classify_encounter, axis=1,
        dead_zone_s=dead_zone_s,
        lead_time_margin_s=lead_time_margin_s,
    )

    tp = int((labels == 'TP').sum())
    fp = int((labels == 'FP').sum())
    tn = int((labels == 'TN').sum())
    fn = int((labels == 'FN').sum())

    total = len(df)
    gt = df['gt_collision'].astype(bool)
    positives = int(gt.sum())
    negatives = total - positives

    tpr = tp / positives if positives > 0 else float('nan')
    fpr = fp / negatives if negatives > 0 else float('nan')
    fnr = fn / positives if positives > 0 else float('nan')
    precision = tp / (tp + fp) if (tp + fp) > 0 else float('nan')

    # Detailed FN breakdown for GT-positive encounters
    gt_pos = df[gt]
    gt_pos_labels = labels[gt]
    gt_pos_det = gt_pos['daa_collision_detected'].astype(bool)
    gt_pos_lead = gt_pos['daa_lead_time_s'] if 'daa_lead_time_s' in gt_pos.columns else pd.Series(dtype=float)
    gt_pos_lookahead = gt_pos['lookahead_s'] if 'lookahead_s' in gt_pos.columns else pd.Series(np.inf, index=gt_pos.index)
    fn_no_alert = int(((gt_pos_labels == 'FN') & (~gt_pos_det)).sum())
    fn_dead_zone = int(((gt_pos_labels == 'FN') & gt_pos_det & (gt_pos_lead < dead_zone_s)).sum())
    fn_unrelated = int(((gt_pos_labels == 'FN') & gt_pos_det & (gt_pos_lead > gt_pos_lookahead + lead_time_margin_s)).sum())

    return {
        'total': total,
        'gt_positive': positives,
        'gt_negative': negatives,
        'TP': tp, 'FP': fp, 'TN': tn, 'FN': fn,
        'FN_no_alert': fn_no_alert,
        'FN_dead_zone': fn_dead_zone,
        'FN_unrelated': fn_unrelated,
        'sensitivity': tpr,
        'specificity': 1 - fpr if not np.isnan(fpr) else float('nan'),
        'precision': precision,
        'false_alarm_rate': fpr,
        'miss_rate': fnr,
        'dead_zone_s': dead_zone_s,
    }


def print_confusion(cm: dict):
    """Pretty-print the zone-aware confusion matrix."""
    print("\n===== Zone-Aware Confusion Matrix =====")
    print(f"  Dead-zone boundary: {cm['dead_zone_s']:.0f}s (alerts below this are FN)")
    print(f"  Total encounters  : {cm['total']}")
    print(f"  GT positives      : {cm['gt_positive']}   GT negatives: {cm['gt_negative']}")
    print()
    print(f"                    Predicted +    Predicted -")
    print(f"  Actual +  (TP)    {cm['TP']:>8d}       (FN) {cm['FN']:>8d}")
    print(f"  Actual -  (FP)    {cm['FP']:>8d}       (TN) {cm['TN']:>8d}")
    print()
    print(f"  FN breakdown (among {cm['gt_positive']} GT-positive encounters):")
    print(f"    No alert at all          : {cm['FN_no_alert']}")
    print(f"    Dead Zone  (<{cm['dead_zone_s']:.0f}s)       : {cm['FN_dead_zone']}")
    print(f"    Unrelated  (>lookahead)  : {cm['FN_unrelated']}")
    print()
    print(f"  Sensitivity  (TPR):  {cm['sensitivity']:.4f}")
    print(f"  Specificity  (TNR):  {cm['specificity']:.4f}")
    print(f"  Precision    (PPV):  {cm['precision']:.4f}")
    print(f"  False alarm  (FPR):  {cm['false_alarm_rate']:.4f}")
    print(f"  Miss rate    (FNR):  {cm['miss_rate']:.4f}")
    print("=" * 40)


# ---------------------------------------------------------------------------
# Breakdown analysis
# ---------------------------------------------------------------------------

def _breakdown(df: pd.DataFrame, column: str, bins=None,
               dead_zone_s: float = DEFAULT_DEAD_ZONE_S,
               lead_time_margin_s: float = DEFAULT_LEAD_TIME_MARGIN_S) -> pd.DataFrame:
    """Compute detection metrics grouped by *column* (or binned if continuous)."""
    work = df.copy()
    if bins is not None:
        work[column + '_bin'] = pd.cut(work[column], bins=bins)
        group_col = column + '_bin'
    else:
        group_col = column

    groups = work.groupby(group_col, observed=True)
    rows = []
    for name, grp in groups:
        cm = compute_confusion(grp, dead_zone_s=dead_zone_s,
                               lead_time_margin_s=lead_time_margin_s)
        rows.append({'group': str(name), 'n': len(grp), **cm})
    return pd.DataFrame(rows)


def breakdown_analysis(df: pd.DataFrame,
                       dead_zone_s: float = DEFAULT_DEAD_ZONE_S,
                       lead_time_margin_s: float = DEFAULT_LEAD_TIME_MARGIN_S,
                       ) -> dict[str, pd.DataFrame]:
    """Return a dict of breakdown DataFrames keyed by the grouping variable."""
    _kw = dict(dead_zone_s=dead_zone_s, lead_time_margin_s=lead_time_margin_s)
    results = {}

    if 'Intruder_azimuth' in df.columns:
        results['azimuth'] = _breakdown(df, 'Intruder_azimuth',
                                        bins=np.arange(0, 391, 30), **_kw)
    if 'Intruder_lateral_offset' in df.columns:
        results['lateral_offset'] = _breakdown(df, 'Intruder_lateral_offset',
                                               bins=[-200, 0, 500, 1000, 2200], **_kw)
    if 'Intruder_vertical_offset' in df.columns:
        results['vertical_offset'] = _breakdown(df, 'Intruder_vertical_offset',
                                                bins=[-100, 0, 100, 225, 300], **_kw)
    if 'Intruder_speed' in df.columns:
        results['intruder_speed'] = _breakdown(df, 'Intruder_speed',
                                               bins=[0, 40, 80, 120, 170], **_kw)
    if 'Ownship_speed' in df.columns:
        results['ownship_speed'] = _breakdown(df, 'Ownship_speed',
                                              bins=[25, 40, 55, 75], **_kw)
    if 'Intruder_category' in df.columns:
        results['intruder_category'] = _breakdown(df, 'Intruder_category', **_kw)
    if 'Ownship_category' in df.columns:
        results['ownship_category'] = _breakdown(df, 'Ownship_category', **_kw)

    return results


# ---------------------------------------------------------------------------
# Plotting (optional)
# ---------------------------------------------------------------------------

def _save_confusion_bar(cm: dict, path: str):
    fig, ax = plt.subplots(figsize=(5, 4))
    labels = ['TP', 'FP', 'TN', 'FN']
    values = [cm[l] for l in labels]
    colors = ['#2ca02c', '#ff7f0e', '#1f77b4', '#d62728']
    ax.bar(labels, values, color=colors)
    ax.set_ylabel('Count')
    ax.set_title('Confusion Matrix')
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_dist_histogram(df: pd.DataFrame, path: str):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    col = 'daa_min_1sigma_cyl_dist'
    if col in df.columns:
        valid = df[col].dropna()
        axes[0].hist(valid, bins=50, edgecolor='black', alpha=0.7)
        axes[0].axvline(1.0, color='red', linestyle='--', label='threshold = 1.0')
        axes[0].set_xlabel('Min 1σ cylinder distance')
        axes[0].set_ylabel('Count')
        axes[0].set_title('DAA Detector — Min Distance Distribution')
        axes[0].legend()

    col = 'gt_min_cyl_dist'
    if col in df.columns:
        valid = df[col].dropna()
        axes[1].hist(valid, bins=50, edgecolor='black', alpha=0.7, color='green')
        axes[1].axvline(1.0, color='red', linestyle='--', label='threshold = 1.0')
        axes[1].set_xlabel('Min actual cylinder distance')
        axes[1].set_ylabel('Count')
        axes[1].set_title('Ground Truth — Min Distance Distribution')
        axes[1].legend()

    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def _save_breakdown_plots(breakdowns: dict, plot_dir: str):
    for key, bd in breakdowns.items():
        if bd.empty:
            continue
        fig, ax = plt.subplots(figsize=(7, 4))
        x = np.arange(len(bd))
        width = 0.35
        ax.bar(x - width/2, bd['sensitivity'].fillna(0), width, label='Sensitivity (TPR)')
        ax.bar(x + width/2, bd['false_alarm_rate'].fillna(0), width, label='False Alarm Rate (FPR)')
        ax.set_xticks(x)
        ax.set_xticklabels(bd['group'], rotation=45, ha='right', fontsize=8)
        ax.set_ylabel('Rate')
        ax.set_title(f'Detection performance by {key}')
        ax.legend()
        ax.set_ylim(0, 1.05)
        fig.tight_layout()
        fig.savefig(os.path.join(plot_dir, f'breakdown_{key}.png'), dpi=150)
        plt.close(fig)


def _save_detection_time_hist(df: pd.DataFrame, path: str,
                              dead_zone_s: float = DEFAULT_DEAD_ZONE_S):
    col = 'daa_lead_time_s'
    if col not in df.columns:
        # Fall back to absolute detection time if lead time not available
        col = 'daa_detection_time_s'
        if col not in df.columns:
            return
        detected = df[df['daa_collision_detected'] == True][col].dropna()  # noqa: E712
        if detected.empty:
            return
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(detected, bins=40, edgecolor='black', alpha=0.7)
        ax.set_xlabel('Detection time (s from encounter start)')
        ax.set_ylabel('Count')
        ax.set_title('Distribution of first detection time')
        fig.tight_layout()
        fig.savefig(path, dpi=150)
        plt.close(fig)
        return

    # Lead-time histogram for GT-positive encounters that got an alert
    gt_pos_alerted = df[(df['gt_collision'] == True) & (df['daa_collision_detected'] == True)]  # noqa: E712
    leads = gt_pos_alerted[col].dropna()
    if leads.empty:
        return
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.hist(leads, bins=40, edgecolor='black', alpha=0.7, color='steelblue')
    # Dead-zone boundary
    ax.axvline(dead_zone_s, color='red', linestyle='--', linewidth=2,
               label=f'Dead Zone boundary ({dead_zone_s:.0f}s)')
    # Shade zones
    ax.axvspan(ax.get_xlim()[0], dead_zone_s, alpha=0.10, color='red', label='Dead Zone')
    ax.axvspan(dead_zone_s, ax.get_xlim()[1], alpha=0.10, color='green', label='Actionable')
    ax.set_xlabel('Alert lead time (s before cylinder penetration)')
    ax.set_ylabel('Count')
    ax.set_title('Lead-Time Distribution (GT-positive encounters with alert)')
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def generate_plots(df: pd.DataFrame, cm: dict,
                   breakdowns: dict, plot_dir: str):
    """Save all analysis plots to *plot_dir*."""
    if not _HAS_MPL:
        print("matplotlib not available — skipping plots.")
        return
    os.makedirs(plot_dir, exist_ok=True)
    _save_confusion_bar(cm, os.path.join(plot_dir, 'confusion_matrix.png'))
    _save_dist_histogram(df, os.path.join(plot_dir, 'distance_histograms.png'))
    _save_breakdown_plots(breakdowns, plot_dir)
    _save_detection_time_hist(
        df, os.path.join(plot_dir, 'lead_time_hist.png'),
        dead_zone_s=cm.get('dead_zone_s', DEFAULT_DEAD_ZONE_S),
    )
    print(f"Plots saved to {plot_dir}/")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Analyze Monte Carlo DAA results',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-i', '--input', required=True,
                        help='Path to montecarlo_results.csv')
    parser.add_argument('--plots', action='store_true',
                        help='Generate analysis plots')
    parser.add_argument('--plot-dir', default='figures',
                        help='Directory for plot output (default: figures/)')
    parser.add_argument('--dead-zone', type=float, default=DEFAULT_DEAD_ZONE_S,
                        help=f'Dead-zone boundary in seconds (default: {DEFAULT_DEAD_ZONE_S}). '
                             'Alerts with lead time below this are counted as FN.')
    parser.add_argument('--lead-margin', type=float, default=DEFAULT_LEAD_TIME_MARGIN_S,
                        help=f'Tolerance above lookahead in seconds (default: {DEFAULT_LEAD_TIME_MARGIN_S}). '
                             'Accounts for discrete time sampling.')
    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: file not found: {args.input}")
        sys.exit(1)

    df = pd.read_csv(args.input)
    # Keep only valid rows
    df = df[df['valid'] == True].copy()  # noqa: E712
    print(f"Loaded {len(df)} valid encounters from {args.input}")

    if df.empty:
        print("No valid encounters to analyze.")
        sys.exit(0)

    # --- Confusion matrix ---
    cm = compute_confusion(df, dead_zone_s=args.dead_zone,
                           lead_time_margin_s=args.lead_margin)
    print_confusion(cm)

    # --- Breakdown analysis ---
    breakdowns = breakdown_analysis(df, dead_zone_s=args.dead_zone,
                                    lead_time_margin_s=args.lead_margin)
    for key, bd in breakdowns.items():
        print(f"\n--- Breakdown by {key} ---")
        print(bd[['group', 'n', 'sensitivity', 'false_alarm_rate', 'miss_rate']].to_string(index=False))

    # --- Plots ---
    if args.plots:
        generate_plots(df, cm, breakdowns, args.plot_dir)


if __name__ == '__main__':
    main()
