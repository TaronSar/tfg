#!/usr/bin/env python3
"""
Monte Carlo DAA evaluation harness.

Runs thousands of randomly-sampled encounters through the full DAA pipeline
(trajectory generation → vision simulation → UKF tracking → 1σ conflict
prediction) and collects per-encounter results into a single CSV / HDF5 file
for subsequent analysis.

Usage
-----
    python run_montecarlo.py --num-encounters 5000 --workers 8 --output results.csv

Key features
------------
* Parallel execution via ``multiprocessing.Pool``.
* Incremental CSV writes — safe to Ctrl-C and resume with ``--resume``.
* Configurable parameter sampling (uniform random, grid, or user-provided).
* Reproducible via ``--master-seed``.
"""

import argparse
import csv
import multiprocessing
import os
import time
import traceback

import numpy as np

from .pipeline import run_single_pipeline


# ---------------------------------------------------------------------------
# Parameter sampling
# ---------------------------------------------------------------------------

# Ranges mirror generate_encounters._default_param_specs() but are designed
# for continuous random sampling rather than a Cartesian grid.
_OWNSHIP_CATEGORIES = ['HB10', 'LU10']
_INTRUDER_CATEGORIES = ['G', 'HB10', 'LU10', 'U']

_PARAM_RANGES = {
    'Ownship_speed':              (30, 70),          # knots
    'Ownship_altitude':           (300, 550),         # feet
    'Ownship_altitude_end':       (300, 550),         # feet
    'Intruder_speed':             (10, 165),          # knots
    'Intruder_altitude':          (300, 550),         # feet
    'Intruder_altitude_end':      (300, 550),         # feet
    'Intruder_azimuth':           (0, 360),           # degrees
    'Intruder_lateral_offset':    (-200, 2200),       # feet  (covers NMAC/WC + margins)
    'Intruder_vertical_offset':   (-100, 275),        # feet  (covers NMAC/WC + margins)
}


def sample_param_spec(rng: np.random.Generator) -> dict:
    """Draw a single random encounter parameter specification."""
    spec = {}

    # Continuous-valued parameters — sample uniformly
    for key, (lo, hi) in _PARAM_RANGES.items():
        val = float(rng.uniform(lo, hi))
        # Speeds and altitudes should be integral
        if 'speed' in key.lower() or 'altitude' in key.lower() or 'azimuth' in key.lower():
            val = int(round(val))
        spec[key] = val

    # Categorical parameters — pick uniformly at random
    spec['Ownship_category'] = rng.choice(_OWNSHIP_CATEGORIES)
    spec['Intruder_category'] = rng.choice(_INTRUDER_CATEGORIES)

    # Fixed / less-interesting parameters
    spec['Path_converging'] = True
    spec['flight_duration'] = 240

    # Make each encounter independently reproducible from its drawn seed
    spec['seed'] = int(rng.integers(0, 2**31))

    return spec


# ---------------------------------------------------------------------------
# Worker function (runs in a child process)
# ---------------------------------------------------------------------------

def _worker(args):
    """Wrapper executed by each pool worker.  Must be a top-level function
    (pickle-able) that accepts a single argument tuple.
    """
    idx, param_spec, estimator_name, lookahead, cyl_h, cyl_d = args
    try:
        result = run_single_pipeline(
            param_spec,
            estimator_name=estimator_name,
            lookahead=lookahead,
            cyl_h=cyl_h,
            cyl_d=cyl_d,
        )
        result['encounter_index'] = idx
        return result
    except Exception:
        return {
            'valid': False,
            'encounter_index': idx,
            'error': traceback.format_exc(),
        }


# ---------------------------------------------------------------------------
# Incremental CSV writer
# ---------------------------------------------------------------------------

class _IncrementalCSVWriter:
    """Append rows to a CSV file, writing the header only once."""

    def __init__(self, path: str, fieldnames: list):
        self.path = path
        self.fieldnames = fieldnames
        write_header = not os.path.exists(path) or os.path.getsize(path) == 0
        self._file = open(path, 'a', newline='', encoding='utf-8')
        self._writer = csv.DictWriter(self._file, fieldnames=fieldnames, extrasaction='ignore')
        if write_header:
            self._writer.writeheader()

    def write_row(self, row: dict):
        self._writer.writerow(row)
        self._file.flush()

    def close(self):
        self._file.close()


# ---------------------------------------------------------------------------
# Determine how many encounters are already done in a resume file
# ---------------------------------------------------------------------------

def _count_existing_rows(path: str) -> int:
    if not os.path.exists(path):
        return 0
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        return max(sum(1 for _ in reader) - 1, 0)  # subtract header


# ---------------------------------------------------------------------------
# Main orchestration
# ---------------------------------------------------------------------------

# Columns written to the output CSV (order matters for readability).
_OUTPUT_COLUMNS = [
    'encounter_index',
    'valid',
    'Ownship_speed', 'Ownship_category', 'Ownship_altitude', 'Ownship_altitude_end',
    'Intruder_speed', 'Intruder_category', 'Intruder_altitude', 'Intruder_altitude_end',
    'Intruder_azimuth', 'Intruder_lateral_offset', 'Intruder_vertical_offset',
    'Path_converging', 'flight_duration', 'seed',
    'estimator', 'lookahead_s', 'CYL_HEIGHT_M', 'CYL_DIAMETER_M',
    # DAA 1σ results
    'daa_collision_detected', 'daa_min_1sigma_cyl_dist', 'daa_detection_time_s',
    # Ground truth
    'gt_collision', 'gt_min_cyl_dist', 'gt_collision_time_s',
    # Alert lead time
    'daa_lead_time_s',
    # Diagnostics
    'error',
]


def run_montecarlo(
    num_encounters: int,
    output_path: str,
    workers: int = 1,
    estimator: str = 'cv',
    lookahead: float = 60.0,
    cyl_h: float = 1000.0,
    cyl_d: float = 2000.0,
    master_seed: int = 42,
    resume: bool = False,
):
    """Generate *num_encounters* random encounters, run each through the full
    DAA pipeline, and save results incrementally to *output_path*.
    """
    rng = np.random.default_rng(master_seed)

    # Pre-draw ALL param-specs (cheap) so that the sequence is deterministic
    # regardless of resume state.
    all_specs = [sample_param_spec(rng) for _ in range(num_encounters)]

    # Resume support — skip already-written rows
    start_idx = 0
    if resume:
        start_idx = _count_existing_rows(output_path)
        if start_idx > 0:
            print(f"Resuming from encounter {start_idx} ({start_idx} already done)")

    remaining = num_encounters - start_idx
    if remaining <= 0:
        print("All encounters already completed.")
        return

    writer = _IncrementalCSVWriter(output_path, _OUTPUT_COLUMNS)

    # Build work items
    work = [
        (i, all_specs[i], estimator, lookahead, cyl_h, cyl_d)
        for i in range(start_idx, num_encounters)
    ]

    t0 = time.time()
    done = 0
    collisions_detected = 0
    gt_collisions = 0

    try:
        if workers <= 1:
            # Single-process for easier debugging
            for item in work:
                result = _worker(item)
                writer.write_row(result)
                done += 1
                if result.get('daa_collision_detected'):
                    collisions_detected += 1
                if result.get('gt_collision'):
                    gt_collisions += 1
                _print_progress(done, remaining, t0, collisions_detected, gt_collisions)
        else:
            # Multiprocessing — use imap_unordered for best throughput
            with multiprocessing.Pool(processes=workers) as pool:
                for result in pool.imap_unordered(_worker, work, chunksize=1):
                    writer.write_row(result)
                    done += 1
                    if result.get('daa_collision_detected'):
                        collisions_detected += 1
                    if result.get('gt_collision'):
                        gt_collisions += 1
                    _print_progress(done, remaining, t0, collisions_detected, gt_collisions)
    except KeyboardInterrupt:
        print(f"\nInterrupted after {done} encounters.  Results saved to {output_path}")
    finally:
        writer.close()

    elapsed = time.time() - t0
    print(f"\nCompleted {done}/{remaining} encounters in {elapsed:.1f}s "
          f"({elapsed/max(done,1):.2f}s/encounter)")
    print(f"Results saved to: {output_path}")


def _print_progress(done, total, t0, detections, gt_collisions):
    elapsed = time.time() - t0
    rate = done / elapsed if elapsed > 0 else 0
    eta = (total - done) / rate if rate > 0 else 0
    print(
        f"\r  [{done}/{total}] {rate:.1f} enc/s | "
        f"DAA detections: {detections} | GT collisions: {gt_collisions} | "
        f"ETA: {eta:.0f}s   ",
        end='', flush=True,
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description='Monte Carlo DAA evaluation',
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('-n', '--num-encounters', type=int, default=1000,
                        help='Total number of encounters to simulate (default: 1000)')
    parser.add_argument('-w', '--workers', type=int,
                        default=min(8, max(1, os.cpu_count() - 1)),
                        help='Number of parallel worker processes (default: CPU count - 1)')
    parser.add_argument('-o', '--output', type=str, default='montecarlo_results.csv',
                        help='Output CSV path (default: montecarlo_results.csv)')
    parser.add_argument('--estimator', type=str, default='cv',
                        choices=['cv', 'ca', 'cab'],
                        help='UKF motion model (default: cv)')
    parser.add_argument('--lookahead', type=float, default=60.0,
                        help='Conflict lookahead horizon in seconds (default: 60)')
    parser.add_argument('--cyl-height', type=float, default=1000.0,
                        help='Protection cylinder height in metres (default: 1000)')
    parser.add_argument('--cyl-diameter', type=float, default=2000.0,
                        help='Protection cylinder diameter in metres (default: 2000)')
    parser.add_argument('--master-seed', type=int, default=42,
                        help='Master RNG seed for reproducibility (default: 42)')
    parser.add_argument('--resume', action='store_true',
                        help='Resume from existing output file')
    args = parser.parse_args()

    run_montecarlo(
        num_encounters=args.num_encounters,
        output_path=args.output,
        workers=args.workers,
        estimator=args.estimator,
        lookahead=args.lookahead,
        cyl_h=args.cyl_height,
        cyl_d=args.cyl_diameter,
        master_seed=args.master_seed,
        resume=args.resume,
    )


if __name__ == '__main__':
    main()
