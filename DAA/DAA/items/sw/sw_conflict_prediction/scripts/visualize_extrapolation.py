#!/usr/bin/env python3
"""
Visualize Extrapolation

Produces a 3D surface plot where:
  X axis = current time (when the prediction is made)
  Y axis = lookahead time (how far into the future we predict)
  Z axis = normalized cylindrical distance at predicted future time

At each (time, lookahead) pair:
  - Intruder position is extrapolated: int_pos(t) + int_vel(t) * lookahead
  - Ownship position is extrapolated: own_pos(t) + own_vel(t) * lookahead
  - The intruder's position covariance is propagated forward by lookahead
  - Cylinder dimensions are expanded by the propagated uncertainty (1-sigma)
  - Normalized cylindrical distance is computed
"""

import pandas as pd
import numpy as np
import argparse
import matplotlib.pyplot as plt
import os
import sys

from estimators import get_estimator_classes


def main():
    parser = argparse.ArgumentParser(
        description="Visualize extrapolation quality as a 3D surface plot"
    )
    parser.add_argument('--ownship', required=True,
                        help='Path to ownship measurements CSV file')
    parser.add_argument('--intruder', required=True,
                        help='Path to intruder recovered trajectory CSV file')
    parser.add_argument('--cylinder-height-ft', type=float, required=True,
                        help='Ownship protected cylinder height in metres')
    parser.add_argument('--cylinder-diameter-ft', type=float, required=True,
                        help='Ownship protected cylinder diameter in metres')
    parser.add_argument('--max-lookahead-s', type=float, default=60.0,
                        help='Maximum lookahead time in seconds (default: 60)')
    parser.add_argument('--lookahead-step-s', type=float, default=1.0,
                        help='Lookahead time step in seconds (default: 1)')
    parser.add_argument('--estimator', type=str, default='cv',
                        choices=['cv', 'ca', 'cab'],
                        help='Estimator model used to produce the intruder CSV (default: cv)')

    args = parser.parse_args()

    # Select estimator class
    estimator_classes = get_estimator_classes()
    estimator_cls = estimator_classes[args.estimator]

    # Validate input files
    for path, label in [(args.ownship, 'Ownship'), (args.intruder, 'Intruder')]:
        if not os.path.exists(path):
            print(f"Error: {label} file not found: {path}")
            sys.exit(1)

    # Load data
    ownship_raw = pd.read_csv(args.ownship)
    intruder_raw = pd.read_csv(args.intruder)

    # Align datasets on common time points
    common_times = np.intersect1d(ownship_raw['time'].values,
                                  intruder_raw['time'].values)
    ownship_data = (ownship_raw[ownship_raw['time'].isin(common_times)]
                    .sort_values('time').reset_index(drop=True))
    intruder_data = (intruder_raw[intruder_raw['time'].isin(common_times)]
                     .sort_values('time').reset_index(drop=True))
    min_len = len(common_times)
    times = ownship_data['time'].values

    # Build lookahead array
    lookaheads = np.arange(0, args.max_lookahead_s + args.lookahead_step_s / 2,
                           args.lookahead_step_s)

    # Create a reusable estimator instance for propagation
    dt_mean = np.mean(np.diff(times)) if len(times) > 1 else 0.1
    estimator = estimator_cls(dt=dt_mean)

    # Compute both surfaces: 0-sigma (constant cylinder) and 1-sigma (expanded)
    Z_0sigma = np.full((len(times), len(lookaheads)), np.nan)
    Z_1sigma = np.full((len(times), len(lookaheads)), np.nan)

    cyl_h_half = args.cylinder_height_ft / 2.0
    cyl_r = args.cylinder_diameter_ft / 2.0

    for i in range(min_len):
        if i % 100 == 0:
            print(f"Processing time step {i}/{min_len}")

        # Ownship state at time t
        own_row = ownship_data.iloc[i]
        own_pos = np.array([own_row['ownship_north_m'],
                            own_row['ownship_east_m'],
                            own_row['ownship_down_m']])
        own_vel = np.array([own_row['ownship_velocity_north_mps'],
                            own_row['ownship_velocity_east_mps'],
                            own_row['ownship_velocity_down_mps']])

        # Intruder state at time t
        int_row = intruder_data.iloc[i]

        # Load state and covariance into the estimator from the CSV row
        estimator.load_state_from_row(int_row)

        batch = estimator.propagate_batch(lookaheads)
        for j, (tau, (int_pos_ext, P_pos_prop)) in enumerate(zip(lookaheads, batch)):
            # Extrapolate ownship position to time t + tau
            own_pos_ext = own_pos + own_vel * tau

            # Relative position at extrapolated time
            rel = int_pos_ext - own_pos_ext

            horiz_dist = np.linalg.norm(rel[:2])

            # 0-sigma: constant cylinder dimensions
            d_z_0 = abs(rel[2]) / cyl_h_half
            d_xy_0 = horiz_dist / cyl_r
            Z_0sigma[i, j] = max(d_z_0, d_xy_0)

            # 1-sigma: expand cylinder with propagated uncertainty

            delta_ne = rel[:2]
            if horiz_dist > 1e-6:
                u = delta_ne / horiz_dist
            else:
                u = np.array([1.0, 0.0])

            P_NE = P_pos_prop[:2, :2]
            radial_var = u @ P_NE @ u
            down_var = P_pos_prop[2, 2]

            radial_std = np.sqrt(max(radial_var, 0.0))
            down_std = np.sqrt(max(down_var, 0.0))

            expanded_h_half = cyl_h_half + down_std
            expanded_r = cyl_r + radial_std

            d_z_1 = abs(rel[2]) / expanded_h_half
            d_xy_1 = horiz_dist / expanded_r
            Z_1sigma[i, j] = max(d_z_1, d_xy_1)

    print(f"Processing complete. Building surface plots...")

    # Create 3D surface plots side by side
    T, L = np.meshgrid(times, lookaheads, indexing='ij')

    fig = plt.figure(figsize=(20, 8))

    # --- Left: 0-sigma (constant cylinder) ---
    ax0 = fig.add_subplot(121, projection='3d')

    surf0 = ax0.plot_surface(T, L, Z_0sigma, cmap='viridis', alpha=0.8, edgecolor='none')

    z_min_0, z_max_0 = np.nanmin(Z_0sigma), np.nanmax(Z_0sigma)
    if z_min_0 < 1.0 < z_max_0:
        ax0.plot_surface(T, L, np.ones_like(T), color='red', alpha=0.15)

    ax0.contour(T, L, Z_0sigma, levels=[1.0], colors='red', linewidths=2)
    ax0.contour(T, L, Z_0sigma, levels=[1.0], colors='red', linewidths=1.5,
                linestyles='dashed', offset=0)

    ax0.set_xlabel('Current Time (s)')
    ax0.set_ylabel('Lookahead (s)')
    ax0.set_zlabel('Normalized Cylindrical Distance')
    ax0.set_zlim(bottom=0)
    ax0.set_title(r'Extrapolated Cylindrical Distance (0$\sigma$)')

    fig.colorbar(surf0, ax=ax0, shrink=0.5, aspect=10, label='Normalized Distance')

    # --- Right: 1-sigma (expanded cylinder) ---
    ax1 = fig.add_subplot(122, projection='3d')

    surf1 = ax1.plot_surface(T, L, Z_1sigma, cmap='viridis', alpha=0.8, edgecolor='none')

    z_min_1, z_max_1 = np.nanmin(Z_1sigma), np.nanmax(Z_1sigma)
    if z_min_1 < 1.0 < z_max_1:
        ax1.plot_surface(T, L, np.ones_like(T), color='red', alpha=0.15)

    ax1.contour(T, L, Z_1sigma, levels=[1.0], colors='red', linewidths=2)
    ax1.contour(T, L, Z_1sigma, levels=[1.0], colors='red', linewidths=1.5,
                linestyles='dashed', offset=0)

    ax1.set_xlabel('Current Time (s)')
    ax1.set_ylabel('Lookahead (s)')
    ax1.set_zlabel('Normalized Cylindrical Distance')
    ax1.set_zlim(bottom=0)
    ax1.set_title(r'Extrapolated Cylindrical Distance (1$\sigma$)')

    fig.colorbar(surf1, ax=ax1, shrink=0.5, aspect=10, label='Normalized Distance')

    plt.tight_layout()
    plt.show()


if __name__ == '__main__':
    main()
