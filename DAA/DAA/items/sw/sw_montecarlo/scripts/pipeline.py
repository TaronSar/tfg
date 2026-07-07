#!/usr/bin/env python3
"""
Single-encounter DAA pipeline: generate → vision → UKF track → 1σ conflict check.

Everything runs in-memory (no intermediate CSV files) for maximum throughput
when called thousands of times in a Monte Carlo loop.
"""

import sys
import os
import contextlib
import numpy as np
import pandas as pd

# ---------------------------------------------------------------------------
# Imports from sibling packages.
# ---------------------------------------------------------------------------
from daa_trajectory_generator.generate_encounters import generate_single_encounter
from daa_conflict_prediction.trajectory_to_vision import calculate_vision_measurements
from daa_conflict_prediction.vision_to_trajectory import VisionTracker
from daa_conflict_prediction.conflict_prediction import ground_truth_collision
from daa_conflict_prediction.estimators import get_estimator_classes

# Resolve estimator classes once at module level
_ESTIMATOR_CLASSES = get_estimator_classes()

# Reusable context manager to silence stdout from library code
_DEVNULL = open(os.devnull, 'w')

@contextlib.contextmanager
def _suppress_stdout():
    old = sys.stdout
    sys.stdout = _DEVNULL
    try:
        yield
    finally:
        sys.stdout = old

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
FT_TO_M = 0.3048  # sw_trajectory_generator outputs feet
LOOKAHEAD_S = 60.0          # Lookahead horizon for collision risk (seconds)
CYL_HEIGHT_M  = 304.8      # Protection cylinder height (metres)
CYL_DIAMETER_M = 609.6    # Protection cylinder diameter (metres)


# ---------------------------------------------------------------------------
# Stage 1: encounter → true-trajectory DataFrame (in-memory)
# ---------------------------------------------------------------------------

def _encounter_to_true_trajectory_df(own_track: dict, intr_track: dict) -> pd.DataFrame:
    """Convert raw encounter track dicts to the true-trajectory DataFrame format
    expected by *trajectory_to_vision.calculate_vision_measurements*.

    The encounter tracks use NED with *up_ft (positive-up, feet); converted to metres. The conflict
    pipeline uses *down* (positive-down).  We convert here.
    """
    n = min(len(own_track['time']), len(intr_track['time']))

    # Decompose ownship speed into NED velocity using attitude angles
    spd = np.asarray(own_track['speed_ftps'][:n], dtype=np.float64) * FT_TO_M  # ft/s -> m/s
    psi = np.asarray(own_track['psi_rad'][:n], dtype=np.float64)
    theta = np.asarray(own_track['theta_rad'][:n], dtype=np.float64)
    phi = np.asarray(own_track['phi_rad'][:n], dtype=np.float64)
    horiz_spd = spd * np.cos(theta)
    own_vn = horiz_spd * np.cos(psi)
    own_ve = horiz_spd * np.sin(psi)
    own_vd = -spd * np.sin(theta)  # NED: positive down, positive theta = nose up = climbing

    rows = {
        'time':                          np.asarray(own_track['time'][:n], dtype=np.float64),
        'ownship_north_m':              np.asarray(own_track['north_ft'][:n], dtype=np.float64) * FT_TO_M,
        'ownship_east_m':               np.asarray(own_track['east_ft'][:n],  dtype=np.float64) * FT_TO_M,
        'ownship_down_m':              -np.asarray(own_track['up_ft'][:n],   dtype=np.float64) * FT_TO_M,
        'ownship_velocity_north_mps':   own_vn,
        'ownship_velocity_east_mps':    own_ve,
        'ownship_velocity_down_mps':    own_vd,
        'ownship_roll_rad':              phi,
        'ownship_pitch_rad':             theta,
        'ownship_yaw_rad':               psi,
        'intruder_north_m':             np.asarray(intr_track['north_ft'][:n], dtype=np.float64) * FT_TO_M,
        'intruder_east_m':              np.asarray(intr_track['east_ft'][:n],  dtype=np.float64) * FT_TO_M,
        'intruder_down_m':             -np.asarray(intr_track['up_ft'][:n],   dtype=np.float64) * FT_TO_M,
    }
    return pd.DataFrame(rows)




# ---------------------------------------------------------------------------
# Stages 3+4 fused: UKF tracking + 1σ conflict detection in one loop.
#
# Uses VisionTracker.track_steps() for the predict/update loop and
# compute_min_1sigma_cylinder_distance() for the per-step conflict check.
# The estimator state (x, P) stays inside the estimator object and is
# never serialised to a DataFrame.
# ---------------------------------------------------------------------------

def _track_and_detect(
    vision_df: pd.DataFrame,
    estimator_name: str = 'cv',
    lookahead: float = LOOKAHEAD_S,
    cyl_h: float = CYL_HEIGHT_M,
    cyl_d: float = CYL_DIAMETER_M,
    process_noise_std: float = 10.0,
) -> dict:
    """Fused UKF tracking + 1σ conflict detection in a single per-step loop.

    Returns a dict with:
    - collision_detected (bool)
    - detection_time     (float, NaN if no alert)
    - min_1sigma_cyl_dist (float)
    """
    if vision_df is None or len(vision_df) == 0:
        return None

    estimator_cls = _ESTIMATOR_CLASSES[estimator_name]
    tracker = VisionTracker(
        process_noise_std=process_noise_std,
        estimator_class=estimator_cls,
        init_window=3,
    )

    global_min = np.inf

    # Sweep used by the cylinder distance scan: 0, 0.5s, 1.0s, ..., lookahead.
    # The ownship is propagated with constant velocity to preserve the
    # previous behaviour.  Pre-build the tau grid once; the per-step ownship
    # trajectory is rebuilt inside the loop from the current own_pos/own_vel.
    sweep_dt = 0.5
    sweep_taus = np.arange(0.0, lookahead + sweep_dt * 0.5, sweep_dt)
    N_sweep = sweep_taus.shape[0]
    # Caller-owned output buffers for the intruder propagation (reused
    # across every step to avoid per-step allocation).
    int_pos_buf = np.empty((N_sweep, 3), dtype=np.float64)
    int_cov_buf = np.empty((N_sweep, 3, 3), dtype=np.float64)

    for estimator, row in tracker.track_steps(vision_df):
        own_pos = np.array([row['ownship_north_m'],
                            row['ownship_east_m'],
                            row['ownship_down_m']])
        own_vel = np.array([row['ownship_velocity_north_mps'],
                            row['ownship_velocity_east_mps'],
                            row['ownship_velocity_down_mps']])

        own_traj = own_pos[None, :] + np.outer(sweep_taus, own_vel)
        # Propagate the intruder once per step; min_1sigma_cylinder_distance
        # now consumes the pre-computed propagation (allows reuse across
        # multiple candidate ownship trajectories in the future).
        propagated = estimator.propagate_batch(sweep_taus.tolist())
        for i, (pos, P) in enumerate(propagated):
            int_pos_buf[i] = pos
            int_cov_buf[i] = P
        d = estimator.min_1sigma_cylinder_distance(
            own_traj, int_pos_buf, int_cov_buf, cyl_h, cyl_d,
        ).min_cyldist
        if d < global_min:
            global_min = d
        if d < 1.0:
            return {
                'collision_detected': True,
                'detection_time': row['time'],
                'min_1sigma_cyl_dist': d,
            }

    return {
        'collision_detected': False,
        'detection_time': np.nan,
        'min_1sigma_cyl_dist': global_min,
    }



# ---------------------------------------------------------------------------
# Full pipeline: one encounter → result dict
# ---------------------------------------------------------------------------

def run_single_pipeline(
    param_spec: dict,
    estimator_name: str = 'cv',
    lookahead: float = LOOKAHEAD_S,
    cyl_h: float = CYL_HEIGHT_M,
    cyl_d: float = CYL_DIAMETER_M,
) -> dict:
    """Run the full DAA pipeline for one encounter and return a result dict.

    Steps:
        1. Generate encounter trajectories (ownship + intruder).
        2. Build true-trajectory DataFrame.
        3. Simulate vision measurements.
        4. Ground-truth collision check (cheap, vectorized).
        5. Fused UKF tracking + 1σ conflict detection (per-step, early exit).

    Returns a flat dict suitable for aggregation into a DataFrame.
    """
    # 1. Generate
    with _suppress_stdout():
        _, args, encounter = generate_single_encounter(param_spec)
    own_track, intr_track = encounter[0], encounter[1]

    # 2. True-trajectory DataFrame
    true_traj_df = _encounter_to_true_trajectory_df(own_track, intr_track)

    # 3. Vision measurements (in-memory, vectorized)
    vision_df = calculate_vision_measurements(true_traj_df)

    # 4. Ground-truth check (cheap, vectorized)
    gt = ground_truth_collision(true_traj_df, cyl_h, cyl_d)

    # 5. Fused UKF tracking + 1σ conflict detection (single loop, no DataFrame)
    q_std = 10.0 if estimator_name in ('cv', 'cv_emb') else 1.0
    with _suppress_stdout():
        conflict = _track_and_detect(
            vision_df, estimator_name, lookahead, cyl_h, cyl_d,
            process_noise_std=q_std,
        )
    if conflict is None:
        return {'valid': False}

    # Extract encounter parameters for the result row
    enc_params = {
        k: getattr(args, k, None)
        for k in (
            'Ownship_speed', 'Ownship_category', 'Ownship_altitude', 'Ownship_altitude_end',
            'Intruder_speed', 'Intruder_category', 'Intruder_altitude', 'Intruder_altitude_end',
            'Intruder_azimuth', 'Intruder_lateral_offset', 'Intruder_vertical_offset',
            'Path_converging', 'flight_duration', 'seed',
        )
    }

    # Lead time: seconds between the DAA alert and the actual cylinder
    # penetration.  detection_time is the encounter clock time when the
    # min-lookahead 1σ distance first drops below 1.0 (i.e. when the alert
    # would appear on screen), NOT the predicted collision time.
    # lead_time = gt_collision_time − detection_time.
    #
    # NOTE: lead_time can exceed the lookahead because the 1σ-inflated
    # cylinder is larger than the real one.  The alert may trigger on a
    # geometry that never materialises on the real cylinder, while the
    # actual collision happens much later.  The analysis script treats
    # lead_time > lookahead as an unrelated alert (FN, not TP).
    daa_det_time = conflict['detection_time']       # absolute time of first alert
    gt_col_time = gt['collision_time']              # absolute time intruder enters cylinder
    if gt['collision'] and not np.isnan(daa_det_time):
        lead_time = gt_col_time - daa_det_time
    else:
        lead_time = np.nan

    return {
        'valid': True,
        **enc_params,
        'estimator': estimator_name,
        'lookahead_s': lookahead,
        'CYL_HEIGHT_M': cyl_h,
        'CYL_DIAMETER_M': cyl_d,
        # DAA detection result (1σ)
        'daa_collision_detected': conflict['collision_detected'],
        'daa_min_1sigma_cyl_dist': conflict['min_1sigma_cyl_dist'],
        'daa_detection_time_s': conflict['detection_time'],
        # Ground truth
        'gt_collision': gt['collision'],
        'gt_min_cyl_dist': gt['min_cyl_dist'],
        'gt_collision_time_s': gt['collision_time'],
        # Alert lead time (seconds before cylinder penetration)
        'daa_lead_time_s': lead_time,
    }
