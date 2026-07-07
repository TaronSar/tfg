#!/usr/bin/env python3
"""
CAA to True Trajectory Script

Converts Canadian Airspace Model output CSV into a true trajectory CSV with
ownship state and intruder position, applying configurable displacement
and rotation transformations to each aircraft.
"""

import pandas as pd
import numpy as np
import argparse
import os
import sys
from typing import Tuple, Optional, Dict

FT_TO_M = 0.3048  # sw_trajectory_generator / CAA outputs in feet


def load_data(csv_file: str) -> pd.DataFrame:
    """Load trajectory data from CSV file."""
    data = pd.read_csv(csv_file)
    print(f"Loaded data with {len(data)} records")
    print(f"Available aircraft IDs: {sorted(data['Aircraft_ID'].unique())}")
    return data


def get_aircraft_trajectory(data: pd.DataFrame, aircraft_id: int) -> pd.DataFrame:
    """Get trajectory data for a specific aircraft, sorted by time."""
    trajectory = data[data['Aircraft_ID'] == aircraft_id].copy()
    if trajectory.empty:
        raise ValueError(f"No trajectory data found for aircraft ID {aircraft_id}")
    return trajectory.sort_values('time').reset_index(drop=True)


def apply_rotation(trajectory: pd.DataFrame, rotation_rad: float) -> pd.DataFrame:
    """
    Apply rotation to trajectory positions and heading around origin [0,0].

    Args:
        trajectory: DataFrame with north_m, east_m, psi_rad columns
        rotation_rad: Rotation angle in radians
    """
    trajectory = trajectory.copy()
    north = trajectory['north_m']
    east = trajectory['east_m']

    cos_a = np.cos(rotation_rad)
    sin_a = np.sin(rotation_rad)

    trajectory['north_m'] = north * cos_a - east * sin_a
    trajectory['east_m'] = north * sin_a + east * cos_a
    trajectory['psi_rad'] = np.fmod(trajectory['psi_rad'] + rotation_rad + np.pi, 2 * np.pi) - np.pi
    return trajectory


def apply_displacement(trajectory: pd.DataFrame,
                       displacement: Tuple[float, float, float]) -> pd.DataFrame:
    """
    Apply displacement (north_m, east_m, up_m) to trajectory positions.
    """
    trajectory = trajectory.copy()
    trajectory['north_m'] += displacement[0]
    trajectory['east_m'] += displacement[1]
    trajectory['up_m'] += displacement[2]
    return trajectory


def interpolate_state(trajectory: pd.DataFrame, time: float) -> Optional[Dict]:
    """Linearly interpolate aircraft state at a given time."""
    if time < trajectory['time'].min() or time > trajectory['time'].max():
        return None

    idx = np.searchsorted(trajectory['time'].values, time)

    if idx == 0:
        return trajectory.iloc[0].to_dict()
    if idx >= len(trajectory):
        return trajectory.iloc[-1].to_dict()

    t1 = trajectory.iloc[idx - 1]['time']
    t2 = trajectory.iloc[idx]['time']
    w = (time - t1) / (t2 - t1) if t2 != t1 else 0.0

    state = {}
    for col in trajectory.columns:
        if col == 'Aircraft_ID':
            state[col] = trajectory.iloc[idx - 1][col]
        else:
            state[col] = trajectory.iloc[idx - 1][col] + w * (
                trajectory.iloc[idx][col] - trajectory.iloc[idx - 1][col]
            )
    return state


def build_true_trajectory(ownship_traj: pd.DataFrame,
                     intruder_traj: pd.DataFrame) -> pd.DataFrame:
    """
    Build the true-trajectory DataFrame from transformed ownship and intruder
    trajectories, interpolating to common time points.
    """
    common_times = np.intersect1d(ownship_traj['time'].values,
                                  intruder_traj['time'].values)

    if len(common_times) == 0:
        min_time = max(ownship_traj['time'].min(), intruder_traj['time'].min())
        max_time = min(ownship_traj['time'].max(), intruder_traj['time'].max())
        common_times = np.linspace(min_time, max_time,
                                   min(len(ownship_traj), len(intruder_traj)))

    rows = []
    for t in common_times:
        own = interpolate_state(ownship_traj, t)
        intr = interpolate_state(intruder_traj, t)
        if own is None or intr is None:
            continue

        # NED velocity from body-frame speed + Euler angles
        speed = own['speed_ftps'] * FT_TO_M
        cos_theta = np.cos(own['theta_rad'])
        sin_theta = np.sin(own['theta_rad'])
        cos_psi = np.cos(own['psi_rad'])
        sin_psi = np.sin(own['psi_rad'])

        rows.append({
            'time': t,
            'ownship_north_m': own['north_m'],
            'ownship_east_m': own['east_m'],
            'ownship_down_m': -own['up_m'],
            'ownship_velocity_north_mps': speed * cos_psi * cos_theta,
            'ownship_velocity_east_mps': speed * sin_psi * cos_theta,
            'ownship_velocity_down_mps': speed * (-sin_theta),
            'ownship_roll_rad': own['phi_rad'],
            'ownship_pitch_rad': own['theta_rad'],
            'ownship_yaw_rad': own['psi_rad'],
            'intruder_north_m': intr['north_m'],
            'intruder_east_m': intr['east_m'],
            'intruder_down_m': -intr['up_m'],
        })

    return pd.DataFrame(rows)


def main():
    parser = argparse.ArgumentParser(
        description='Convert Canadian Airspace Model CSV to true-trajectory CSV')

    parser.add_argument('--input', '-i', required=True,
                        help='Input CSV file (CAA format)')
    parser.add_argument('--output', '-o', required=True,
                        help='Output true-trajectory CSV file')
    parser.add_argument('--ownship-id', type=int, required=True,
                        help='Aircraft_ID of the ownship')
    parser.add_argument('--intruder-id', type=int, required=True,
                        help='Aircraft_ID of the intruder')

    parser.add_argument('--ownship-displacement', nargs=3, type=float,
                        default=[0, 0, 0],
                        help='Ownship displacement [north_m east_m up_m]')
    parser.add_argument('--ownship-rotation', type=float, default=0,
                        help='Ownship rotation angle in degrees')
    parser.add_argument('--intruder-displacement', nargs=3, type=float,
                        default=[0, 0, 0],
                        help='Intruder displacement [north_m east_m up_m]')
    parser.add_argument('--intruder-rotation', type=float, default=0,
                        help='Intruder rotation angle in degrees')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        sys.exit(1)

    data = load_data(args.input)

    available_ids = sorted(data['Aircraft_ID'].unique())
    for label, aid in [('Ownship', args.ownship_id),
                       ('Intruder', args.intruder_id)]:
        if aid not in available_ids:
            print(f"Error: {label} aircraft ID {aid} not found. "
                  f"Available IDs: {available_ids}")
            sys.exit(1)

    if args.ownship_id == args.intruder_id:
        print("Error: Ownship and intruder aircraft must be different")
        sys.exit(1)

    ownship_traj = get_aircraft_trajectory(data, args.ownship_id)
    intruder_traj = get_aircraft_trajectory(data, args.intruder_id)

    # Convert CAA output columns from feet to metres at the boundary
    for _traj in [ownship_traj, intruder_traj]:
        _traj['north_m'] = _traj['north_ft'] * FT_TO_M
        _traj['east_m'] = _traj['east_ft'] * FT_TO_M
        _traj['up_m'] = _traj['up_ft'] * FT_TO_M

    print(f"Ownship trajectory: {len(ownship_traj)} points")
    print(f"Intruder trajectory: {len(intruder_traj)} points")

    # Rotation first, then displacement (same order as trajectory_to_vision.py)
    own_rot = np.radians(args.ownship_rotation)
    intr_rot = np.radians(args.intruder_rotation)
    own_disp = tuple(args.ownship_displacement)
    intr_disp = tuple(args.intruder_displacement)

    if args.ownship_rotation != 0:
        ownship_traj = apply_rotation(ownship_traj, own_rot)
    if args.intruder_rotation != 0:
        intruder_traj = apply_rotation(intruder_traj, intr_rot)
    if any(own_disp):
        ownship_traj = apply_displacement(ownship_traj, own_disp)
    if any(intr_disp):
        intruder_traj = apply_displacement(intruder_traj, intr_disp)

    print("Building true-trajectory table...")
    result = build_true_trajectory(ownship_traj, intruder_traj)

    if result.empty:
        print("Warning: No common time points found between ownship and intruder")
        sys.exit(1)

    result.to_csv(args.output, index=False)
    print(f"Saved {len(result)} rows to {args.output}")


if __name__ == "__main__":
    main()
