#!/usr/bin/env python3
"""
Trajectory to Vision Measurement Script

This script reads a true-trajectory CSV (produced by caa_to_true_trajectory.py) that
already contains the transformed ownship state and intruder position, and
calculates azimuth, elevation, and range measurements that a forward-pointing
camera mounted on the ownship would obtain when observing the intruder.

Input CSV columns:
    time, ownship_north_m, ownship_east_m, ownship_down_m,
    ownship_velocity_north_mps, ownship_velocity_east_mps,
    ownship_velocity_down_mps, ownship_roll_rad, ownship_pitch_rad,
    ownship_yaw_rad, intruder_north_m, intruder_east_m, intruder_down_m

Output CSV columns:
    time, ownship_north_m, ownship_east_m, ownship_down_m,
    ownship_velocity_north_mps, ownship_velocity_east_mps,
    ownship_velocity_down_mps, ownship_roll_rad, ownship_pitch_rad,
    ownship_yaw_rad, azimuth_rad, elevation_rad, range_m
"""

import pandas as pd
import numpy as np
import argparse
import os
import sys


def ned_to_body_frame(relative_position: np.ndarray,
                      roll: float, pitch: float, yaw: float) -> np.ndarray:
    """
    Convert NED (North-East-Down) coordinates to aircraft body frame.

    Args:
        relative_position: [north, east, down] vector in NED frame
        roll: Roll angle in radians (phi)
        pitch: Pitch angle in radians (theta)
        yaw: Yaw angle in radians (psi)

    Returns:
        [x, y, z] vector in body frame (x=forward, y=right, z=down)
    """
    cos_psi, sin_psi = np.cos(yaw), np.sin(yaw)
    cos_theta, sin_theta = np.cos(pitch), np.sin(pitch)
    cos_phi, sin_phi = np.cos(roll), np.sin(roll)

    if abs(roll) < 1e-10 and abs(pitch) < 1e-10:
        R_nb = np.array([
            [cos_psi,  sin_psi,  0],
            [-sin_psi, cos_psi,  0],
            [0,        0,        1]
        ])
    else:
        # Full 3D rotation matrix (3-2-1 Euler sequence)
        R_nb = np.array([
            [cos_psi * cos_theta,
             sin_psi * cos_theta,
             -sin_theta],
            [-sin_psi * cos_phi + cos_psi * sin_theta * sin_phi,
             cos_psi * cos_phi + sin_psi * sin_theta * sin_phi,
             cos_theta * sin_phi],
            [sin_psi * sin_phi + cos_psi * sin_theta * cos_phi,
             -cos_psi * sin_phi + sin_psi * sin_theta * cos_phi,
             cos_theta * cos_phi]
        ])

    return R_nb @ relative_position


def calculate_vision_measurements(data: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate azimuth, elevation, and range from a true-trajectory DataFrame.

    Fully vectorized — operates on entire arrays in one pass via numpy.
    Each row must contain ownship state and intruder NED position.
    """
    # Relative position in NED
    rel_n = data['intruder_north_m'].values - data['ownship_north_m'].values
    rel_e = data['intruder_east_m'].values - data['ownship_east_m'].values
    rel_d = data['intruder_down_m'].values - data['ownship_down_m'].values

    # Trig of ownship attitude (all arrays of length N)
    cp = np.cos(data['ownship_yaw_rad'].values)
    sp = np.sin(data['ownship_yaw_rad'].values)
    ct = np.cos(data['ownship_pitch_rad'].values)
    st = np.sin(data['ownship_pitch_rad'].values)
    cr = np.cos(data['ownship_roll_rad'].values)
    sr = np.sin(data['ownship_roll_rad'].values)

    # Full 3-2-1 rotation NED->body, applied element-wise
    x_body = cp * ct * rel_n + sp * ct * rel_e - st * rel_d
    y_body = (-sp * cr + cp * st * sr) * rel_n + \
             ( cp * cr + sp * st * sr) * rel_e + \
             ct * sr * rel_d
    z_body = ( sp * sr + cp * st * cr) * rel_n + \
             (-cp * sr + sp * st * cr) * rel_e + \
             ct * cr * rel_d

    # Spherical measurements
    range_m = np.sqrt(x_body**2 + y_body**2 + z_body**2)
    azimuth_rad = np.arctan2(y_body, x_body)
    horiz_dist = np.sqrt(x_body**2 + y_body**2)
    elevation_rad = np.arctan2(-z_body, horiz_dist)

    return pd.DataFrame({
        'time': data['time'].values,
        'ownship_north_m': data['ownship_north_m'].values,
        'ownship_east_m': data['ownship_east_m'].values,
        'ownship_down_m': data['ownship_down_m'].values,
        'ownship_velocity_north_mps': data['ownship_velocity_north_mps'].values,
        'ownship_velocity_east_mps': data['ownship_velocity_east_mps'].values,
        'ownship_velocity_down_mps': data['ownship_velocity_down_mps'].values,
        'ownship_roll_rad': data['ownship_roll_rad'].values,
        'ownship_pitch_rad': data['ownship_pitch_rad'].values,
        'ownship_yaw_rad': data['ownship_yaw_rad'].values,
        'azimuth_rad': azimuth_rad,
        'elevation_rad': elevation_rad,
        'range_m': range_m,
    })


def main():
    """Main function to process true-trajectory CSV and generate vision measurements."""
    parser = argparse.ArgumentParser(
        description='Calculate vision measurements from a true-trajectory CSV')

    parser.add_argument('--input', '-i', required=True,
                        help='Input true-trajectory CSV file (from caa_to_true_trajectory.py)')
    parser.add_argument('--output', '-out',
                        help='Output CSV file for vision measurements')

    args = parser.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        sys.exit(1)

    try:
        print("Loading true-trajectory data...")
        data = pd.read_csv(args.input)
        print(f"Loaded {len(data)} rows")

        print("Calculating vision measurements...")
        measurements = calculate_vision_measurements(data)

        if measurements.empty:
            print("Warning: No vision measurements could be calculated")
            sys.exit(1)

        print(f"Calculated {len(measurements)} vision measurements")

        # Save results
        if args.output:
            output_file = args.output
        else:
            base_name = os.path.splitext(args.input)[0]
            output_file = f"{base_name}_vision_measurements.csv"

        measurements.to_csv(output_file, index=False)
        print(f"Vision measurements saved to: {output_file}")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
