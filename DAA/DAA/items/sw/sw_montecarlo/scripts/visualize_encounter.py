#!/usr/bin/env python3
"""
Replay and visualize a single encounter from Monte Carlo results.

Given a results CSV and an encounter seed, this script:
  1. Reconstructs the encounter parameters from the CSV row.
  2. Re-runs the pipeline stages to produce the intermediate DataFrames.
  3. Launches visualize_trajectories.py for interactive animation (all in-memory).

Usage:
    python visualize_encounter.py --csv results_cv.csv --index 0
    python visualize_encounter.py --csv results_cv.csv --index 3
"""

import argparse
import sys

import pandas as pd

# ---------------------------------------------------------------------------
# Imports from this and sibling packages.
# ---------------------------------------------------------------------------
from .pipeline import (
    _encounter_to_true_trajectory_df,
    _suppress_stdout,
    CYL_HEIGHT_M, CYL_DIAMETER_M,
)
from daa_conflict_prediction.trajectory_to_vision import calculate_vision_measurements
from daa_trajectory_generator.generate_encounters import generate_single_encounter
from daa_conflict_prediction.conflict_prediction import ConflictAnalyzer, classify_result, fn_sub_reason, DEFAULT_DEAD_ZONE_S, DEFAULT_LEAD_TIME_MARGIN_S
from daa_conflict_prediction.estimators import get_estimator_classes
from daa_conflict_prediction.visualize_trajectories import TrajectoryVisualizer
from .analyze_results import classify_encounter

_ESTIMATOR_CLASSES = get_estimator_classes()

# Columns that define the encounter param_spec (must match run_montecarlo.py)
_PARAM_KEYS = [
    'Ownship_speed', 'Ownship_category', 'Ownship_altitude', 'Ownship_altitude_end',
    'Intruder_speed', 'Intruder_category', 'Intruder_altitude', 'Intruder_altitude_end',
    'Intruder_azimuth', 'Intruder_lateral_offset', 'Intruder_vertical_offset',
    'Path_converging', 'flight_duration', 'seed',
]


def row_to_param_spec(row: pd.Series) -> dict:
    """Reconstruct the param_spec dict from a CSV row."""
    spec = {}
    for key in _PARAM_KEYS:
        val = row[key]
        # Ensure correct types expected by generate_single_encounter
        if key in ('Ownship_speed', 'Intruder_speed', 'Intruder_azimuth',
                    'Ownship_altitude', 'Ownship_altitude_end',
                    'Intruder_altitude', 'Intruder_altitude_end',
                    'flight_duration', 'seed'):
            val = int(val)
        elif key == 'Path_converging':
            val = bool(val)
        else:
            val = float(val) if not isinstance(val, str) else val
        spec[key] = val
    return spec


def _conflict_results_to_df(results: dict, cyl_h: float, cyl_d: float) -> pd.DataFrame:
    """Convert ConflictAnalyzer.analyze_encounter() dict to a DataFrame."""
    data = {
        'time': results['times'],
        'ownship_cylinder_height_m': cyl_h,
        'ownship_cylinder_diameter_m': cyl_d,
        '0_sigma_cylinder_distance_current': results['0_sigma_cylinder_distance_current'],
        '1_sigma_cylinder_distance_current': results['1_sigma_cylinder_distance_current'],
        '1_sigma_cylinder_distance_min_lookahead': results['1_sigma_cylinder_distance_min_lookahead'],
        'radial_variance_ft2': results['radial_variance_ft2'],
        'down_variance_ft2': results['down_variance_ft2'],
        'tcpa_seconds': results['tcpa_values'],
        'intruder_north_at_tcpa': results['intruder_north_at_tcpa'],
        'intruder_east_at_tcpa': results['intruder_east_at_tcpa'],
        'intruder_down_at_tcpa': results['intruder_down_at_tcpa'],
        '0_sigma_cylinder_distance_at_tcpa': results['0_sigma_cylinder_distance_at_tcpa'],
        'tcross_seconds': results['tcross_seconds'],
        'intruder_north_at_tcross': results['intruder_north_at_tcross'],
        'intruder_east_at_tcross': results['intruder_east_at_tcross'],
        'intruder_down_at_tcross': results['intruder_down_at_tcross'],
        '0_sigma_cylinder_distance_at_tcross': results['0_sigma_cylinder_distance_at_tcross'],
    }
    for dt in ConflictAnalyzer.LOOKAHEAD_SECONDS:
        data[f'intruder_north_at_t_plus_{dt}'] = results[f'intruder_north_at_t_plus_{dt}']
        data[f'intruder_east_at_t_plus_{dt}'] = results[f'intruder_east_at_t_plus_{dt}']
        data[f'intruder_down_at_t_plus_{dt}'] = results[f'intruder_down_at_t_plus_{dt}']
        data[f'radial_variance_ft2_at_t_plus_{dt}'] = results[f'radial_variance_ft2_at_t_plus_{dt}']
        data[f'down_variance_ft2_at_t_plus_{dt}'] = results[f'down_variance_ft2_at_t_plus_{dt}']
    return pd.DataFrame(data)


def main():
    parser = argparse.ArgumentParser(
        description="Replay and visualize a single Monte Carlo encounter.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--csv", required=True,
                        help="Path to Monte Carlo results CSV")
    parser.add_argument("--index", required=True, type=int,
                        help="Row index (0-based) in the CSV to replay")
    parser.add_argument("--frame-step", type=int, default=5,
                        help="Render every Nth frame (default: 5)")
    parser.add_argument("--show-uncertainty", action="store_true", default=True,
                        help="Show uncertainty ellipsoids (default: True)")
    parser.add_argument("--dead-zone", type=float, default=DEFAULT_DEAD_ZONE_S,
                        help=f"Dead-zone boundary in seconds (default: {DEFAULT_DEAD_ZONE_S})")
    parser.add_argument("--lead-margin", type=float, default=DEFAULT_LEAD_TIME_MARGIN_S,
                        help=f"Margin above lookahead for TP (default: {DEFAULT_LEAD_TIME_MARGIN_S})")
    args = parser.parse_args()

    # --- 1. Find the encounter row ---
    df = pd.read_csv(args.csv)
    matches = df[df['encounter_index'] == args.index]
    if matches.empty:
        valid_indices = sorted(df['encounter_index'].unique())
        print(f"Error: encounter_index {args.index} not found in {args.csv}")
        print(f"  Available indices: {valid_indices[:20]}{'...' if len(valid_indices) > 20 else ''}")
        sys.exit(1)
    row = matches.iloc[0]

    estimator_name = str(row.get('estimator', 'cv'))
    cyl_h = float(row.get('CYL_HEIGHT_M', CYL_HEIGHT_M))
    cyl_d = float(row.get('CYL_DIAMETER_M', CYL_DIAMETER_M))

    param_spec = row_to_param_spec(row)
    seed = int(row.get('seed', 0))
    print(f"Replaying encounter  index={args.index}  seed={seed}  estimator={estimator_name}")
    print(f"  Ownship : {param_spec['Ownship_category']}  {param_spec['Ownship_speed']} kts  "
          f"alt (ft, generator input)")
    print(f"  Intruder: {param_spec['Intruder_category']}  {param_spec['Intruder_speed']} kts  "
          f"az {param_spec['Intruder_azimuth']}°  lat_off {param_spec['Intruder_lateral_offset']:.0f} ft")

    # --- 2. Re-generate the encounter ---
    print("Generating encounter trajectories...")
    with _suppress_stdout():
        _, enc_args, encounter = generate_single_encounter(param_spec)
    own_track, intr_track = encounter[0], encounter[1]

    # --- 3. Build intermediate DataFrames (all in-memory) ---
    print("Building true trajectory...")
    true_traj_df = _encounter_to_true_trajectory_df(own_track, intr_track)

    print("Simulating vision measurements...")
    vision_df = calculate_vision_measurements(true_traj_df)

    print(f"Running UKF tracking + conflict prediction ({estimator_name.upper()})...")
    estimator_cls = _ESTIMATOR_CLASSES[estimator_name]
    q_std = 10.0 if estimator_name in ('cv',) else 1.0
    analyzer = ConflictAnalyzer(
        cylinder_height=cyl_h, cylinder_diameter=cyl_d,
        estimator_class=estimator_cls,
        process_noise_std=q_std,
    )
    with _suppress_stdout():
        results = analyzer.analyze_encounter(vision_df)
    conflict_df = _conflict_results_to_df(results, cyl_h, cyl_d)

    # Build recovered trajectory DataFrame for the visualizer
    recovered_df = analyzer.tracker.run_tracking(vision_df)

    # --- 4. Launch visualizer (in-memory) ---
    cm_class = classify_encounter(row, args.dead_zone, args.lead_margin)
    gt_coll = bool(row.get('gt_collision', False))
    daa_det = bool(row.get('daa_collision_detected', False))
    lead = row.get('daa_lead_time_s', float('nan'))
    lookahead = row.get('lookahead_s', float('inf'))

    _CM_LABELS = {
        'TP': ('TRUE POSITIVE', 'green'),
        'FP': ('FALSE POSITIVE', 'orange'),
        'TN': ('TRUE NEGATIVE', 'green'),
        'FN': ('FALSE NEGATIVE', 'red'),
    }
    cm_label, cm_color = _CM_LABELS[cm_class]

    # Append FN sub-reason when applicable
    if cm_class == 'FN':
        reason = fn_sub_reason(daa_det, lead, lookahead, args.dead_zone, args.lead_margin)
        if reason:
            cm_label += f' ({reason})'

    max_lead = lookahead + args.lead_margin
    lead_str = f'{lead:.1f}s (max {max_lead:.0f})' if not pd.isna(lead) else 'N/A'
    print(f"\nGT collision: {gt_coll}   DAA detected: {daa_det}   lead: {lead_str}   [{cm_label}]")
    print("Launching visualizer...\n")

    vis_title = (f'Encounter #{args.index}  [{cm_label}]  —  '
                 f'GT collision: {gt_coll}  |  DAA detected: {daa_det}  |  lead: {lead_str}')

    visualizer = TrajectoryVisualizer(
        true_traj_df,
        vision_df,
        recovered_df,
        conflict_df,
        show_uncertainty=args.show_uncertainty,
        uncertainty_scale=1.0,
        title=vis_title,
    )
    visualizer.load_and_process_data()
    visualizer.run_animation(frame_step=args.frame_step)


if __name__ == "__main__":
    main()
