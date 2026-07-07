#!/usr/bin/env python3
"""
Generate simple test trajectories with constant velocity for testing.

Output CSVs match the true-trajectory format produced by caa_to_true_trajectory.py.
"""

import numpy as np
import pandas as pd
import argparse

# Simulation parameters
DT = 0.1          # period in seconds
T_END = 250.0     # end time in seconds
ALTITUDE_M = -914.4  # ownship_down_m (negative = above ground)


def _integrate_step(state, centripetal_accel):
    """Advance one Euler step. Returns updated [n, e, d, vn, ve, vd].

    centripetal_accel > 0 turns right (clockwise in NE top-down).
    """
    n, e, d, vn, ve, vd = state
    if centripetal_accel != 0.0:
        speed_ne = np.sqrt(vn**2 + ve**2)
        if speed_ne > 0:
            an = -centripetal_accel * ve / speed_ne
            ae =  centripetal_accel * vn / speed_ne
        else:
            an = ae = 0.0
    else:
        an = ae = 0.0
    vn += an * DT
    ve += ae * DT
    n += vn * DT
    e += ve * DT
    d += vd * DT
    return [n, e, d, vn, ve, vd]


def generate_trajectory(
    ownship_pos, ownship_vel,
    intruder_pos, intruder_vel,
    output_file,
    ownship_centripetal_accel=0.0,
    intruder_centripetal_accel=0.0,
):
    """
    Generate a trajectory CSV with optional centripetal acceleration.

    Args:
        ownship_pos: (north_m, east_m, down_m)
        ownship_vel: (vn_ftps, ve_ftps, vd_ftps)
        intruder_pos: (north_m, east_m, down_m)
        intruder_vel: (vn_ftps, ve_ftps, vd_ftps)
        output_file: path to write the CSV
        ownship_centripetal_accel: perpendicular accel (m/s²), >0 = right turn
        intruder_centripetal_accel: perpendicular accel (m/s²), >0 = right turn
    """
    times = np.arange(0.0, T_END + DT / 2, DT)

    own = list(ownship_pos) + list(ownship_vel)
    intr = list(intruder_pos) + list(intruder_vel)

    rows = []
    for t in times:
        on, oe, od, ovn, ove, ovd = own
        inn, ie, id_, ivn, ive, ivd = intr
        ownship_yaw = np.arctan2(ove, ovn)

        rows.append({
            'time': round(t, 6),
            'ownship_north_m': on,
            'ownship_east_m': oe,
            'ownship_down_m': od,
            'ownship_velocity_north_mps': ovn,
            'ownship_velocity_east_mps': ove,
            'ownship_velocity_down_mps': ovd,
            'ownship_roll_rad': 0.0,
            'ownship_pitch_rad': 0.0,
            'ownship_yaw_rad': ownship_yaw,
            'intruder_north_m': inn,
            'intruder_east_m': ie,
            'intruder_down_m': id_,
        })

        own = _integrate_step(own, ownship_centripetal_accel)
        intr = _integrate_step(intr, intruder_centripetal_accel)

    df = pd.DataFrame(rows)
    df.to_csv(output_file, index=False)
    print(f"Saved {len(df)} rows to {output_file}")


def main():
    # Speed (m/s) — roughly 70 kts
    speed = 36.576
    half_time = T_END / 2.0
    # Distance each aircraft covers in half the simulation
    half_dist = speed * half_time
    east_offset = 152.4  # m

    # Registry of available scenarios: name -> (kwargs for generate_trajectory)
    scenarios = {
        'front_collision': {
            'ownship_pos': (-half_dist, 0.0, ALTITUDE_M),
            'ownship_vel': (speed, 0.0, 0.0),
            'intruder_pos': (half_dist, 0.0, ALTITUDE_M),
            'intruder_vel': (-speed, 0.0, 0.0),
        },
        'front_parallel_miss': {
            'ownship_pos': (-half_dist, 0.0, ALTITUDE_M),
            'ownship_vel': (speed, 0.0, 0.0),
            'intruder_pos': (half_dist, east_offset, ALTITUDE_M),
            'intruder_vel': (-speed, 0.0, 0.0),
        },
        'perpendicular_collision': {
            'ownship_pos': (-half_dist, 0.0, ALTITUDE_M),
            'ownship_vel': (speed, 0.0, 0.0),
            'intruder_pos': (0.0, -half_dist, ALTITUDE_M),
            'intruder_vel': (0.0, speed, 0.0),
        },
        'perpendicular_miss': {
            'ownship_pos': (-speed * 180.0, 0.0, ALTITUDE_M),
            'ownship_vel': (speed, 0.0, 0.0),
            'intruder_pos': (0.0, -speed * 160.0, ALTITUDE_M),
            'intruder_vel': (0.0, speed, 0.0),
        },
        'chase_miss': {
            'ownship_pos': (-half_dist, 0.0, ALTITUDE_M),
            'ownship_vel': (speed, 0.0, 0.0),
            'intruder_pos': (-half_dist + 1524.0, 0.0, ALTITUDE_M),
            'intruder_vel': (speed * 1.5, 0.0, 0.0),
        },
        'chase_catch': {
            'ownship_pos': (-half_dist, 0.0, ALTITUDE_M),
            'ownship_vel': (speed, 0.0, 0.0),
            'intruder_pos': (-half_dist + 1524.0, 0.0, ALTITUDE_M),
            'intruder_vel': (speed * 0.75, 0.0, 0.0),
        },
        'circular_cross': {
            'ownship_pos': (-speed * 180.0, 0.0, ALTITUDE_M),
            'ownship_vel': (speed, 0.0, 0.0),
            'intruder_pos': (0.0, -1219.2, ALTITUDE_M),
            'intruder_vel': (speed, 0.0, 0.0),
            'intruder_centripetal_accel': speed**2 / 1219.2,  # R=1219.2 m, right turn
        },
    }

    parser = argparse.ArgumentParser(description='Generate test true-trajectory CSVs')
    parser.add_argument('--scenario', choices=list(scenarios.keys()), required=True,
                        help='Scenario to generate')
    parser.add_argument('--output', required=True,
                        help='Output CSV file path')
    args = parser.parse_args()

    generate_trajectory(**scenarios[args.scenario], output_file=args.output)


if __name__ == '__main__':
    main()
