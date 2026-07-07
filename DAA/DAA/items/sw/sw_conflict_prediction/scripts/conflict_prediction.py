#!/usr/bin/env python3
"""
Conflict Prediction Script

This script implements the conflict prediction logic from the C++ source code to compute
the Time of Closest Point of Approach (TCPA) between ownship and intruder aircraft.

It reads:
- Ownship position and velocity from a measurements CSV file
- Intruder position and velocity from a recovered trajectory CSV file

The script implements the cylinder distance calculation and TCPA computation
as defined in the original C++ Conflict_prediction class.
"""

import pandas as pd
import numpy as np
import argparse
from typing import Tuple, Dict
import sys
import os

from .estimators import get_estimator_classes
from .vision_to_trajectory import VisionTracker


class CylinderDistance:
    """
    Represents the relative position and velocity between two aircraft
    and provides methods to compute cylinder-based separation distances.
    """
    
    def __init__(self, p: np.ndarray, v: np.ndarray, cyl_h: float, cyl_d: float):
        """
        Initialize cylinder distance calculator.
        
        Args:
            p: Relative position vector [north, east, up] in metres
            v: Relative velocity vector [vn, ve, vu] in m/s  
            cyl_h: Cylinder height (vertical separation) in metres
            cyl_d: Cylinder diameter (horizontal separation) in metres
        """
        self.p = np.array(p, dtype=np.float64)
        self.v = np.array(v, dtype=np.float64)
        self.cyl_h = float(cyl_h)
        self.cyl_d = float(cyl_d)
    
    def compute_at(self, t: float) -> float:
        """
        Compute normalized cylinder distance at time t.
        
        Args:
            t: Time in seconds
            
        Returns:
            Normalized cylinder distance (max of vertical and horizontal components)
        """
        # Position at time t: d = p + v*t
        d = self.p + self.v * t
        
        # Vertical cylinder distance (normalized by half height)
        d_cyl_z = abs(d[2]) / self.cyl_h
        
        # Horizontal cylinder distance (normalized by radius)
        d_horizontal = np.sqrt(d[0]**2 + d[1]**2)
        d_cyl_xy = d_horizontal / self.cyl_d
        
        # Return maximum (most restrictive)
        return max(d_cyl_z, d_cyl_xy)


class TcpaSelector:
    """
    Helper class to select the time with minimum cylinder distance.
    """
    
    def __init__(self, cpi: CylinderDistance, tmax: float):
        """
        Initialize TCPA selector.
        
        Args:
            cpi: CylinderDistance instance
            tmax: Maximum time to consider
        """
        self.cpi = cpi
        self.tmax = tmax
        self.dist = cpi.compute_at(0.0)
        self.t = 0.0
    
    def push(self, t0: float) -> None:
        """
        Consider a candidate time for minimum distance.
        
        Args:
            t0: Candidate time
        """
        if 0.0 <= t0 <= self.tmax:
            dist0 = self.cpi.compute_at(t0)
            if dist0 < self.dist or (dist0 == self.dist and t0 < self.t):
                self.dist = dist0
                self.t = t0


class ConflictPredictor:
    """
    Main class implementing conflict prediction algorithms.
    """
    
    @staticmethod
    def compute_tcpa(cpi: CylinderDistance, tmax: float) -> float:
        """
        Compute time of closest point of approach within time horizon.
        
        This method implements the algorithm from the C++ source code,
        finding critical points where the cylinder distance might be minimized.
        
        Args:
            cpi: CylinderDistance instance
            tmax: Maximum time horizon in seconds
            
        Returns:
            Time of closest point of approach in seconds
        """
        # Initialize selector with t=0
        tcpa_sel = TcpaSelector(cpi, tmax)
        
        # Point of interest 1: t = tmax
        tcpa_sel.push(tmax)
        
        eps_vz = 1e-6
        eps_vxy2 = 1e-12
        eps_a = 1e-6
        eps_b = 1e-6
        
        # Point of interest 2: Minimizing vertical component
        vz = cpi.v[2]
        pz = cpi.p[2]
        if abs(vz) > eps_vz:
            tcpa_sel.push(-pz / vz)
        
        # Point of interest 3: Minimizing horizontal component
        nvxy2 = cpi.v[0]**2 + cpi.v[1]**2
        pxy_vxy = cpi.p[0] * cpi.v[0] + cpi.p[1] * cpi.v[1]
        if nvxy2 > eps_vxy2:
            tcpa_sel.push(-pxy_vxy / nvxy2)
        
        # Points of interest 4 and 5: Solutions of quadratic equation
        h2 = cpi.cyl_h**2
        d2 = cpi.cyl_d**2
        a = (vz**2) / h2 - nvxy2 / d2
        b = 2.0 * ((pz * vz) / h2 - pxy_vxy / d2)
        c = (pz**2) / h2 - (cpi.p[0]**2 + cpi.p[1]**2) / d2
        
        if abs(a) > eps_a:
            discriminant = b**2 - 4.0 * a * c
            if discriminant >= 0.0:
                sqrt_discriminant = np.sqrt(discriminant)
                two_a = 2.0 * a
                tcpa_sel.push((-b + sqrt_discriminant) / two_a)
                tcpa_sel.push((-b - sqrt_discriminant) / two_a)
        elif abs(b) > eps_b:
            tcpa_sel.push(-c / b)
        
        return tcpa_sel.t


class ConflictAnalyzer:
    """Conflict prediction analyzer.

    Runs UKF tracking via :class:`VisionTracker` internally so there is no
    need for a separate intruder-trajectory CSV.  The estimator state (x, P)
    is read directly from the live estimator object.
    """

    LOOKAHEAD_SECONDS = [15, 30, 45, 60]
    LOOKAHEAD_SWEEP_DT = 0.5  # seconds between evaluation points

    def __init__(self, cylinder_height: float = 1000.0,
                 cylinder_diameter: float = 2000.0,
                 estimator_class=None,
                 process_noise_std: float = 10.0,
                 measurement_noise_std=None,
                 init_window: int = 3):
        self.cylinder_height = cylinder_height
        self.cylinder_diameter = cylinder_diameter
        self.estimator_class = estimator_class or get_estimator_classes()['cv']
        self.tracker = VisionTracker(
            process_noise_std=process_noise_std,
            measurement_noise_std=measurement_noise_std,
            estimator_class=self.estimator_class,
            init_window=init_window,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _find_tcross(self, cpi, tcpa, scan_step=1.0, tol=0.01):
        """Earliest lookahead time where cylinder distance first crosses below 1."""
        f0 = cpi.compute_at(0.0)
        if f0 < 1.0:
            return 0.0
        lo = 0.0
        t = scan_step
        while t <= tcpa:
            m = cpi.compute_at(t)
            if m < 1.0:
                lo = t - scan_step
                break
            t += scan_step
        else:
            lo = t - scan_step
        hi = min(t, tcpa)
        for _ in range(50):
            if hi - lo < tol:
                break
            mid = (lo + hi) / 2.0
            if cpi.compute_at(mid) >= 1.0:
                lo = mid
            else:
                hi = mid
        return hi

    @staticmethod
    def _compute_radial_down_variance(P_pos, rel_pos_future):
        """Compute radial and down variances from propagated position covariance."""
        horiz_dist = np.sqrt(rel_pos_future[0]**2 + rel_pos_future[1]**2)
        if horiz_dist > 1e-6:
            u = np.array([rel_pos_future[0], rel_pos_future[1]]) / horiz_dist
        else:
            u = np.array([1.0, 0.0])
        radial_var = u @ P_pos[:2, :2] @ u
        down_var = P_pos[2, 2]
        return radial_var, down_var

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------
    def analyze_encounter(self, measurements_df,
                          time_horizon: float = 300.0,
                          save_trajectory: str = None) -> Dict:
        """Run UKF tracking + full conflict analysis in a single pass.

        Args:
            measurements_df: Vision-measurements DataFrame (the combined
                ownship + intruder measurements produced by
                ``trajectory_to_vision``).
            time_horizon: Maximum TCPA horizon in seconds.
            save_trajectory: If given, save the recovered intruder
                trajectory CSV at this path (for visualization).

        Returns:
            Dictionary with per-step conflict metrics.
        """
        results = {
            'times': [],
            '0_sigma_cylinder_distance_current': [],
            '1_sigma_cylinder_distance_current': [],
            '1_sigma_cylinder_distance_min_lookahead': [],
            'radial_variance_ft2': [],
            'down_variance_ft2': [],
            'tcpa_values': [],
            'intruder_north_at_tcpa': [],
            'intruder_east_at_tcpa': [],
            'intruder_down_at_tcpa': [],
            '0_sigma_cylinder_distance_at_tcpa': [],
            'tcross_seconds': [],
            'intruder_north_at_tcross': [],
            'intruder_east_at_tcross': [],
            'intruder_down_at_tcross': [],
            '0_sigma_cylinder_distance_at_tcross': [],
        }
        for dt in self.LOOKAHEAD_SECONDS:
            results[f'intruder_north_at_t_plus_{dt}'] = []
            results[f'intruder_east_at_t_plus_{dt}'] = []
            results[f'intruder_down_at_t_plus_{dt}'] = []
            results[f'radial_variance_ft2_at_t_plus_{dt}'] = []
            results[f'down_variance_ft2_at_t_plus_{dt}'] = []

        trajectory_rows = [] if save_trajectory else None
        step_count = 0

        for estimator, row in self.tracker.track_steps(measurements_df):
            step_count += 1
            if step_count % 100 == 0:
                print(f"\rProcessed {step_count} time steps", end='', flush=True)

            # --- ownship state (from measurement row) ---
            own_pos = np.array([row['ownship_north_m'],
                                row['ownship_east_m'],
                                row['ownship_down_m']])
            own_vel = np.array([row['ownship_velocity_north_mps'],
                                row['ownship_velocity_east_mps'],
                                row['ownship_velocity_down_mps']])

            # --- intruder state (from live estimator) ---
            state = estimator.get_state_dict()
            int_pos = np.array([state['intruder_north_m'],
                                state['intruder_east_m'],
                                state['intruder_down_m']])
            int_vel = np.array([state['intruder_vn_ftps'],
                                state['intruder_ve_ftps'],
                                state['intruder_vd_ftps']])
            P_full = estimator.P

            # --- relative kinematics ---
            rel_pos = int_pos - own_pos
            rel_vel = int_vel - own_vel

            # --- 0-sigma cylinder distance (current) ---
            cpi = CylinderDistance(rel_pos, rel_vel,
                                  self.cylinder_height / 2.0,
                                  self.cylinder_diameter / 2.0)
            current_cyl_dist_0sigma = cpi.compute_at(0.0)

            # --- 1-sigma cylinder distance (current) ---
            P_pos_current = P_full[:3, :3]
            rad_var_current, down_var_current = self._compute_radial_down_variance(
                P_pos_current, rel_pos)
            radial_std = np.sqrt(rad_var_current)
            down_std = np.sqrt(down_var_current)
            cpi_1sigma = CylinderDistance(
                rel_pos, rel_vel,
                self.cylinder_height / 2.0 + down_std,
                self.cylinder_diameter / 2.0 + radial_std)
            current_cyl_dist_1sigma = cpi_1sigma.compute_at(0.0)

            # --- TCPA ---
            tcpa = ConflictPredictor.compute_tcpa(cpi, time_horizon)
            [(intruder_pos_at_tcpa, _)] = estimator.propagate_batch([tcpa])
            cyl_dist_at_tcpa = cpi.compute_at(tcpa)

            # --- tcross ---
            if cyl_dist_at_tcpa < 1.0:
                tcross = self._find_tcross(cpi, tcpa)
                [(intruder_pos_at_tcross, _)] = estimator.propagate_batch([tcross])
                tcross_val = tcross
                tcross_north = intruder_pos_at_tcross[0]
                tcross_east = intruder_pos_at_tcross[1]
                tcross_down = intruder_pos_at_tcross[2]
                cyl_dist_at_tcross = cpi.compute_at(tcross)
            else:
                tcross_val = np.nan
                tcross_north = tcross_east = tcross_down = np.nan
                cyl_dist_at_tcross = np.nan

            # --- min 1-sigma lookahead ---
            lookahead = max(self.LOOKAHEAD_SECONDS)
            sweep_dt = self.LOOKAHEAD_SWEEP_DT
            sweep_taus = np.arange(0.0, lookahead + sweep_dt * 0.5, sweep_dt)
            own_traj = np.asarray(own_pos)[None, :] + np.outer(
                sweep_taus, np.asarray(own_vel))
            int_pos_buf = np.empty((sweep_taus.size, 3), dtype=np.float64)
            int_cov_buf = np.empty((sweep_taus.size, 3, 3), dtype=np.float64)
            for i, (pos, P) in enumerate(
                    estimator.propagate_batch(sweep_taus.tolist())):
                int_pos_buf[i] = pos
                int_cov_buf[i] = P
            min_1sigma_lookahead = estimator.min_1sigma_cylinder_distance(
                own_traj, int_pos_buf, int_cov_buf,
                self.cylinder_height, self.cylinder_diameter,
            ).min_cyldist

            # --- store step results ---
            results['times'].append(row['time'])
            results['0_sigma_cylinder_distance_current'].append(current_cyl_dist_0sigma)
            results['1_sigma_cylinder_distance_current'].append(current_cyl_dist_1sigma)
            results['1_sigma_cylinder_distance_min_lookahead'].append(min_1sigma_lookahead)
            results['radial_variance_ft2'].append(radial_std**2)
            results['down_variance_ft2'].append(down_std**2)
            results['tcpa_values'].append(tcpa)
            results['intruder_north_at_tcpa'].append(intruder_pos_at_tcpa[0])
            results['intruder_east_at_tcpa'].append(intruder_pos_at_tcpa[1])
            results['intruder_down_at_tcpa'].append(intruder_pos_at_tcpa[2])
            results['0_sigma_cylinder_distance_at_tcpa'].append(cyl_dist_at_tcpa)
            results['tcross_seconds'].append(tcross_val)
            results['intruder_north_at_tcross'].append(tcross_north)
            results['intruder_east_at_tcross'].append(tcross_east)
            results['intruder_down_at_tcross'].append(tcross_down)
            results['0_sigma_cylinder_distance_at_tcross'].append(cyl_dist_at_tcross)

            # --- lookahead predictions ---
            batch = estimator.propagate_batch(self.LOOKAHEAD_SECONDS)
            for dt, (future_int_pos, P_pos) in zip(self.LOOKAHEAD_SECONDS, batch):
                rel_pos_future = rel_pos + rel_vel * dt
                rad_var, down_var = self._compute_radial_down_variance(
                    P_pos, rel_pos_future)
                results[f'intruder_north_at_t_plus_{dt}'].append(future_int_pos[0])
                results[f'intruder_east_at_t_plus_{dt}'].append(future_int_pos[1])
                results[f'intruder_down_at_t_plus_{dt}'].append(future_int_pos[2])
                results[f'radial_variance_ft2_at_t_plus_{dt}'].append(rad_var)
                results[f'down_variance_ft2_at_t_plus_{dt}'].append(down_var)

            # --- optional trajectory row ---
            if trajectory_rows is not None:
                trow = {'time': row['time']}
                trow.update(state)
                for ci in range(estimator.dim_x):
                    for cj in range(ci, estimator.dim_x):
                        trow[f'P_{ci}{cj}'] = P_full[ci, cj]
                trajectory_rows.append(trow)

        print(f"\rProcessed {step_count} time steps")

        if save_trajectory and trajectory_rows:
            pd.DataFrame(trajectory_rows).to_csv(save_trajectory, index=False)
            print(f"Recovered trajectory saved to: {save_trajectory}")

        return results

    def save_results(self, results: Dict, output_file: str) -> None:
        """Save analysis results to CSV file."""
        data = {
            'time': results['times'],
            'ownship_cylinder_height_m': self.cylinder_height,
            'ownship_cylinder_diameter_m': self.cylinder_diameter,
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
        for dt in self.LOOKAHEAD_SECONDS:
            data[f'intruder_north_at_t_plus_{dt}'] = results[f'intruder_north_at_t_plus_{dt}']
            data[f'intruder_east_at_t_plus_{dt}'] = results[f'intruder_east_at_t_plus_{dt}']
            data[f'intruder_down_at_t_plus_{dt}'] = results[f'intruder_down_at_t_plus_{dt}']
            data[f'radial_variance_ft2_at_t_plus_{dt}'] = results[f'radial_variance_ft2_at_t_plus_{dt}']
            data[f'down_variance_ft2_at_t_plus_{dt}'] = results[f'down_variance_ft2_at_t_plus_{dt}']
        df = pd.DataFrame(data)
        df.to_csv(output_file, index=False)
        print(f"Results saved to: {output_file}")



# ---------------------------------------------------------------------------
# Ground-truth collision check (true, noise-free trajectories)
# ---------------------------------------------------------------------------
DEFAULT_DEAD_ZONE_S = 15.0        # alerts < 15 s before collision are too late
DEFAULT_LEAD_TIME_MARGIN_S = 5.0  # tolerance above lookahead for discrete sampling


def ground_truth_collision(
    true_traj_df: pd.DataFrame,
    cyl_h: float,
    cyl_d: float,
) -> dict:
    """Check whether the intruder *actually* entered the protection cylinder
    at any point during the encounter, using the true (noise-free) positions.

    Returns dict with keys:
    - collision:        True if the intruder entered the cylinder
    - min_cyl_dist:     minimum cylinder distance over the whole encounter
    - collision_time:   time (s) when the intruder first enters the cylinder
                        (NaN if no collision)
    """
    times = true_traj_df['time'].values
    rel_n = true_traj_df['intruder_north_m'].values - true_traj_df['ownship_north_m'].values
    rel_e = true_traj_df['intruder_east_m'].values  - true_traj_df['ownship_east_m'].values
    rel_d = true_traj_df['intruder_down_m'].values  - true_traj_df['ownship_down_m'].values

    half_h = cyl_h / 2.0
    radius = cyl_d / 2.0

    d_z = np.abs(rel_d) / half_h
    d_xy = np.sqrt(rel_n**2 + rel_e**2) / radius
    d_inst = np.maximum(d_z, d_xy)

    min_dist = d_inst.min() if len(d_inst) else np.inf
    inside = np.where(d_inst < 1.0)[0]
    collision_time = times[inside[0]] if len(inside) else np.nan

    return {
        'collision': min_dist < 1.0,
        'min_cyl_dist': min_dist,
        'collision_time': collision_time,
    }


def classify_result(
    gt_collision: bool,
    detected: bool,
    lead_time_s: float,
    lookahead_s: float,
    dead_zone_s: float = DEFAULT_DEAD_ZONE_S,
    lead_time_margin_s: float = DEFAULT_LEAD_TIME_MARGIN_S,
) -> str:
    """Classify a single encounter outcome into TP / FP / TN / FN.

    This is the pure-scalar version of the zone-aware classification.

    Zone rules when *gt_collision* is True:
      - Alert with dead_zone_s <= lead_time <= lookahead + margin -> TP
      - Alert with lead_time < dead_zone_s                       -> FN (dead zone)
      - Alert with lead_time > lookahead + margin                -> FN (unrelated)
      - No alert at all                                          -> FN

    When *gt_collision* is False:
      - System alerts -> FP
      - System silent -> TN
    """
    if not gt_collision:
        return 'FP' if detected else 'TN'

    if not detected:
        return 'FN'

    if np.isnan(lead_time_s):
        return 'FN'

    if dead_zone_s <= lead_time_s <= lookahead_s + lead_time_margin_s:
        return 'TP'
    return 'FN'


def fn_sub_reason(
    detected: bool,
    lead_time_s: float,
    lookahead_s: float,
    dead_zone_s: float = DEFAULT_DEAD_ZONE_S,
    lead_time_margin_s: float = DEFAULT_LEAD_TIME_MARGIN_S,
) -> str:
    """Return a human-readable FN sub-reason string (empty if N/A)."""
    if not detected:
        return 'no alert'
    if np.isnan(lead_time_s):
        return 'no alert'
    if lead_time_s < dead_zone_s:
        return 'dead zone'
    if lead_time_s > lookahead_s + lead_time_margin_s:
        return 'unrelated'
    return ''


def main():
    """Main function with command line interface."""
    parser = argparse.ArgumentParser(
        description="Conflict Prediction Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python conflict_prediction.py --input examples/example_measurements.csv --output results.csv --estimator cab
        """
    )

    parser.add_argument('--input', '-i', required=True,
                       help='Path to vision-measurements CSV file')
    parser.add_argument('--output', '-o',
                       help='Output CSV file for conflict results')
    parser.add_argument('--save-trajectory',
                       help='Optional: save recovered intruder trajectory CSV '
                            '(for visualization)')
    parser.add_argument('--ownship-cylinder-height-m', type=float, default=1000.0,
                       help='Protected cylinder height in metres (default: 1000)')
    parser.add_argument('--ownship-cylinder-diameter-m', type=float, default=2000.0,
                       help='Protected cylinder diameter in metres (default: 2000)')
    parser.add_argument('--time-horizon', type=float, default=300.0,
                       help='Maximum time horizon in seconds (default: 300)')
    parser.add_argument('--estimator', type=str, default='cv',
                       choices=['cv', 'ca', 'cab'],
                       help='Estimator model to use (default: cv)')
    parser.add_argument('--process-noise-std', type=float, default=None,
                       help='Process noise standard deviation '
                            '(default: 10.0 for cv, 1.0 for ca/cab)')
    args = parser.parse_args()

    # Auto-select process noise default based on estimator model
    if args.process_noise_std is None:
        args.process_noise_std = 1.0 if args.estimator in ('ca', 'cab') else 10.0

    if not os.path.exists(args.input):
        print(f"Error: Input file not found: {args.input}")
        sys.exit(1)

    try:
        estimator_classes = get_estimator_classes()
        measurements_df = pd.read_csv(args.input)
        print(f"Loaded {len(measurements_df)} measurements from {args.input}")

        analyzer = ConflictAnalyzer(
            cylinder_height=args.ownship_cylinder_height_m,
            cylinder_diameter=args.ownship_cylinder_diameter_m,
            estimator_class=estimator_classes[args.estimator],
            process_noise_std=args.process_noise_std,
        )

        print("Analyzing encounter...")
        results = analyzer.analyze_encounter(
            measurements_df,
            time_horizon=args.time_horizon,
            save_trajectory=args.save_trajectory,
        )

        print(f"\n=== Conflict Analysis Summary ===")
        print(f"Total analysis duration: {results['times'][-1]:.1f} seconds")

        if args.output:
            analyzer.save_results(results, args.output)

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
