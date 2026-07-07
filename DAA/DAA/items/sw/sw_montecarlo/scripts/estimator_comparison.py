#!/usr/bin/env python3
"""
Run a comparative Monte Carlo analysis across the CV, CA, and CAB estimators.

Usage:
    python run_example.py                      # 20 encounters, all defaults
    python run_example.py -n 100               # 100 encounters
    python run_example.py -n 50 --master-seed 7

All three models are run on the *same* set of randomly generated encounters
(same --master-seed), so the results are directly comparable.
"""

import argparse
import ctypes
import os
import platform
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_SCRIPT_DIR = Path(__file__).resolve().parent
_RUN_MC = _SCRIPT_DIR / "run_montecarlo.py"
_ANALYZE = _SCRIPT_DIR / "analyze_results.py"

from .analyze_results import (
    compute_confusion,
    DEFAULT_DEAD_ZONE_S,
    DEFAULT_LEAD_TIME_MARGIN_S,
)

ESTIMATORS = ["cv", "ca", "cab"]


def _prevent_sleep():
    """Prevent the OS from sleeping while the simulation runs (Windows only)."""
    if platform.system() == "Windows":
        ES_CONTINUOUS = 0x80000000
        ES_SYSTEM_REQUIRED = 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(
            ES_CONTINUOUS | ES_SYSTEM_REQUIRED
        )


def run_model(estimator: str, n: int, master_seed: int, output_dir: Path,
              workers: int):
    """Run the Monte Carlo for one estimator and return the output CSV path."""
    out_csv = output_dir / f"results_{estimator}.csv"
    # Remove stale file to avoid --resume picking up old data
    if out_csv.exists():
        out_csv.unlink()

    cmd = [
        sys.executable, str(_RUN_MC),
        "-n", str(n),
        "-w", str(workers),
        "-o", str(out_csv),
        "--estimator", estimator,
        "--master-seed", str(master_seed),
    ]
    print(f"\n{'='*60}")
    print(f"  Running {estimator.upper()} model  ({n} encounters, {workers} workers)")
    print(f"{'='*60}")
    subprocess.run(cmd, check=True)
    return out_csv


def load_results(csv_path: Path) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    return df[df.get("valid", True) != False].reset_index(drop=True)


def print_comparison_table(results: dict[str, pd.DataFrame],
                          dead_zone_s: float = DEFAULT_DEAD_ZONE_S,
                          lead_time_margin_s: float = DEFAULT_LEAD_TIME_MARGIN_S):
    """Print a side-by-side zone-aware confusion-matrix comparison."""
    metrics = {}
    for name, df in results.items():
        metrics[name] = compute_confusion(df, dead_zone_s, lead_time_margin_s)

    # Header
    header = f"{'Metric':<22}" + "".join(f"{e.upper():>12}" for e in ESTIMATORS)
    print(f"\n{'='*60}")
    print("  MODEL COMPARISON  (zone-aware)")
    print(f"  Dead zone: {dead_zone_s:.0f}s   Lead-time margin: {lead_time_margin_s:.0f}s")
    print(f"{'='*60}")
    print(header)
    print("-" * len(header))

    n_enc = len(next(iter(results.values())))

    rows = [
        ("TP",              "TP",              None),
        ("FP",              "FP",              None),
        ("TN",              "TN",              None),
        ("FN",              "FN",              None),
        ("  FN no alert",   "FN_no_alert",     None),
        ("  FN dead zone",  "FN_dead_zone",    None),
        ("  FN unrelated",  "FN_unrelated",    None),
        ("Sensitivity",     "sensitivity",     ".4f"),
        ("Specificity",     "specificity",     ".4f"),
        ("Precision",       "precision",       ".4f"),
        ("False alarm rate","false_alarm_rate", ".4f"),
        ("Miss rate",       "miss_rate",       ".4f"),
    ]
    for label, key, fmt in rows:
        parts = [f"{label:<22}"]
        for e in ESTIMATORS:
            v = metrics[e][key]
            if fmt is None:
                parts.append(f"{f'{v}/{n_enc}':>12}")
            elif isinstance(v, float) and np.isnan(v):
                parts.append(f"{'N/A':>12}")
            else:
                parts.append(f"{v:>12{fmt}}")
        print("".join(parts))

    # Ground-truth positives (same across models)
    any_df = next(iter(results.values()))
    gt_pos = int(any_df["gt_collision"].astype(bool).sum())
    gt_neg = len(any_df) - gt_pos
    print(f"\n  Encounters: {len(any_df)}  (GT+: {gt_pos}, GT-: {gt_neg})")


def print_per_encounter_table(results: dict[str, pd.DataFrame]):
    """Print a per-encounter comparison of 1σ minimum distances."""
    ref = next(iter(results.values()))
    cols = {
        "azimuth": ref["Intruder_azimuth"],
        "lat_off": ref["Intruder_lateral_offset"],
        "gt_coll": ref["gt_collision"],
        "gt_min": ref["gt_min_cyl_dist"],
    }
    for name, df in results.items():
        cols[f"{name}_det"] = df["daa_collision_detected"]
        cols[f"{name}_min"] = df["daa_min_1sigma_cyl_dist"]

    cmp = pd.DataFrame(cols)
    pd.set_option("display.width", 250)
    pd.set_option("display.float_format", "{:.3f}".format)

    print(f"\n{'='*60}")
    print("  PER-ENCOUNTER DETAIL")
    print(f"{'='*60}")
    print(cmp.to_string())


def main():
    parser = argparse.ArgumentParser(
        description="Compare CV, CA, and CAB estimators on the same encounters.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-n", "--num-encounters", type=int, default=20,
                        help="Number of encounters (default: 20)")
    parser.add_argument("-w", "--workers", type=int,
                        default=min(8, max(1, os.cpu_count() - 1)),
                        help="Parallel workers (default: CPU count - 1)")
    parser.add_argument("--master-seed", type=int, default=100,
                        help="Master RNG seed (default: 100)")
    parser.add_argument("-o", "--output-dir", type=str, default=None,
                        help="Directory for result CSVs (default: sw_montecarlo/example_results/)")
    parser.add_argument("--dead-zone", type=float, default=DEFAULT_DEAD_ZONE_S,
                        help=f"Dead-zone boundary in seconds (default: {DEFAULT_DEAD_ZONE_S})")
    parser.add_argument("--lead-margin", type=float, default=DEFAULT_LEAD_TIME_MARGIN_S,
                        help=f"Margin above lookahead for TP (default: {DEFAULT_LEAD_TIME_MARGIN_S})")
    args = parser.parse_args()

    _prevent_sleep()

    output_dir = Path(args.output_dir) if args.output_dir else (
        Path(__file__).resolve().parents[1] / "example_results"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    # Run all three models on the same encounters
    csv_paths = {}
    for est in ESTIMATORS:
        csv_paths[est] = run_model(est, args.num_encounters, args.master_seed,
                                   output_dir, args.workers)

    # Load results
    results = {est: load_results(path) for est, path in csv_paths.items()}

    # Print comparison
    print_comparison_table(results, args.dead_zone, args.lead_margin)
    print_per_encounter_table(results)

    print(f"\nCSV files saved in: {output_dir}")


if __name__ == "__main__":
    main()
