#!/usr/bin/env python3
"""
Vision-based Intruder Tracking

This script processes vision measurements (azimuth, elevation, range) from an ownship
aircraft and estimates the intruder's trajectory using a configurable state estimator.
"""

import numpy as np
import pandas as pd
import argparse
import sys
import os

from .estimators import get_estimator_classes

ESTIMATOR_CLASSES = get_estimator_classes()


class VisionTracker:
    """Main class for processing vision measurements and tracking intruders."""
    
    def __init__(self, process_noise_std=10.0, measurement_noise_std=None,
                 estimator_class=None, init_window=3):
        """
        Initialize tracker with noise parameters.
        
        Args:
            process_noise_std: Standard deviation for process noise (ft and m/s)
            measurement_noise_std: Dict with measurement noise stds
            estimator_class: StateEstimator subclass to use for tracking
            init_window: Number of measurements to buffer for initial velocity
                estimation. Must be >= 2.  Set to 1 to disable (zero-velocity init).
        """
        self.process_noise_std = process_noise_std
        if estimator_class is None:
            estimator_class = ESTIMATOR_CLASSES['cv']
        self.estimator_class = estimator_class
        self.init_window = max(init_window, 1)
        
        # Default measurement noise standard deviations
        if measurement_noise_std is None:
            self.measurement_noise_std = {
                'azimuth_rad': 0.02,     # ~1.1 degrees
                'elevation_rad': 0.02,   # ~1.1 degrees  
                'range_m': 15.24        # 15.24 m (= 50 ft)
            }
        else:
            self.measurement_noise_std = measurement_noise_std
            
    def load_measurements(self, csv_file):
        """Load vision measurements from CSV file."""
        try:
            df = pd.read_csv(csv_file)
            print(f"Loaded {len(df)} measurements from {csv_file}")
            
            # Verify required columns
            required_cols = ['time', 'ownship_north_m', 'ownship_east_m', 'ownship_down_m',
                           'ownship_roll_rad', 'ownship_pitch_rad', 'ownship_yaw_rad', 
                           'azimuth_rad', 'elevation_rad', 'range_m']
            
            missing_cols = [col for col in required_cols if col not in df.columns]
            if missing_cols:
                raise ValueError(f"Missing required columns: {missing_cols}")
                
            return df.sort_values('time').reset_index(drop=True)
            
        except Exception as e:
            print(f"Error loading measurements: {e}")
            return None
    
    def _compute_initial_position(self, first_measurement):
        """Compute initial intruder position in NED from the first spherical measurement."""
        ownship_pos = np.array([first_measurement['ownship_north_m'],
                               first_measurement['ownship_east_m'],
                               first_measurement['ownship_down_m']])
        ownship_att = np.array([first_measurement['ownship_roll_rad'],
                               first_measurement['ownship_pitch_rad'],
                               first_measurement['ownship_yaw_rad']])

        azimuth = first_measurement['azimuth_rad']
        elevation = first_measurement['elevation_rad']
        range_dist = first_measurement['range_m']

        # Convert polar measurement to Cartesian estimate in ownship body frame
        x_body = range_dist * np.cos(elevation) * np.cos(azimuth)
        y_body = range_dist * np.cos(elevation) * np.sin(azimuth)
        z_body = -range_dist * np.sin(elevation)  # Negative because positive elevation means target is above horizontal

        # Transform to NED frame
        roll, pitch, yaw = ownship_att
        cos_roll, sin_roll = np.cos(roll), np.sin(roll)
        cos_pitch, sin_pitch = np.cos(pitch), np.sin(pitch)
        cos_yaw, sin_yaw = np.cos(yaw), np.sin(yaw)

        # Rotation from body to NED frame (transpose of NED to body)
        north = cos_pitch * cos_yaw * x_body + \
                (sin_roll * sin_pitch * cos_yaw - cos_roll * sin_yaw) * y_body + \
                (cos_roll * sin_pitch * cos_yaw + sin_roll * sin_yaw) * z_body

        east = cos_pitch * sin_yaw * x_body + \
               (sin_roll * sin_pitch * sin_yaw + cos_roll * cos_yaw) * y_body + \
               (cos_roll * sin_pitch * sin_yaw - sin_roll * cos_yaw) * z_body

        down = -sin_pitch * x_body + sin_roll * cos_pitch * y_body + cos_roll * cos_pitch * z_body

        return ownship_pos + np.array([north, east, down])

    def initialize_filter(self, first_measurement, dt, initial_velocity=None,
                          position_variance=1000.0, velocity_variance=100.0):
        """Initialize state estimator with first measurement and optional velocity."""
        initial_position = self._compute_initial_position(first_measurement)
        estimator = self.estimator_class(dt=dt)
        estimator.initialize(initial_position, dt, self.process_noise_std,
                             self.measurement_noise_std,
                             position_variance=position_variance,
                             initial_velocity=initial_velocity,
                             velocity_variance=velocity_variance)
        return estimator

    def _estimate_initial_velocity(self, buffer_rows):
        """Estimate velocity via least-squares fit through buffered NED positions.

        Args:
            buffer_rows: List of measurement rows (pandas Series).

        Returns:
            (pos0, last_position, velocity) — all np.ndarray of shape (3,).
            pos0 is the fitted position at the first buffered time.
        """
        times = np.array([r['time'] for r in buffer_rows])
        positions = np.array([self._compute_initial_position(r) for r in buffer_rows])

        # Centre times at zero for numerical stability
        t0 = times[0]
        t_rel = times - t0

        # Least-squares fit:  pos = pos0 + vel * t   →  [1, t] @ [pos0, vel]^T = pos
        A = np.column_stack([np.ones(len(t_rel)), t_rel])
        # Solve for each axis independently (or all at once)
        params, _, _, _ = np.linalg.lstsq(A, positions, rcond=None)
        # params[0] = pos0 (position at t0), params[1] = velocity
        velocity = params[1]
        pos0 = params[0]

        # Return the position at the *last* buffered time (best estimate)
        last_pos = pos0 + velocity * t_rel[-1]
        return pos0, last_pos, velocity
    
    def run_tracking(self, measurements_df, output_file=None):
        """Run state estimation on measurement sequence."""
        if measurements_df is None or len(measurements_df) == 0:
            print("No measurements to process")
            return None
            
        # Calculate time steps
        times = measurements_df['time'].values
        dt_values = np.diff(times)
        dt_mean = np.mean(dt_values) if len(dt_values) > 0 else 0.1
        
        print(f"Processing {len(measurements_df)} measurements")
        print(f"Time range: {times[0]:.1f} - {times[-1]:.1f} s")
        print(f"Average dt: {dt_mean:.3f} s")
        
        # Storage for results (one row per input measurement)
        results = []

        for estimator, row in self.track_steps(measurements_df):
            # Store results — state columns from estimator, covariance upper triangle
            result = {'time': row['time']}
            result.update(estimator.get_state_dict())
            for ci in range(estimator.dim_x):
                for cj in range(ci, estimator.dim_x):
                    result[f'P_{ci}{cj}'] = estimator.P[ci, cj]
            results.append(result)
        
        # Convert to DataFrame
        results_df = pd.DataFrame(results)
        
        # Save results
        if output_file:
            results_df.to_csv(output_file, index=False)
            print(f"Tracking results saved to: {output_file}")
        
        return results_df

    def track_steps(self, measurements_df):
        """Generator that yields (estimator, measurement_row) after each
        predict+update step.

        The estimator object holds the current state (x, P) and can be
        queried directly — no serialisation needed.  This allows callers
        to process each step without building a full DataFrame.
        """
        if measurements_df is None or len(measurements_df) == 0:
            return

        times = measurements_df['time'].values
        dt_values = np.diff(times)
        dt_mean = np.mean(dt_values) if len(dt_values) > 0 else 0.1

        # ------------------------------------------------------------------
        # Initialisation: buffer the first N measurements to estimate velocity
        # ------------------------------------------------------------------
        n_buf = min(self.init_window, len(measurements_df))

        if n_buf >= 2:
            buffer_rows = [measurements_df.iloc[j] for j in range(n_buf)]
            _, init_pos, init_vel = self._estimate_initial_velocity(buffer_rows)
            estimator = self.estimator_class(dt=dt_mean)
            estimator.initialize(init_pos, dt_mean, self.process_noise_std,
                                 self.measurement_noise_std,
                                 position_variance=1000.0,
                                 initial_velocity=init_vel,
                                 velocity_variance=10.0)
            start_idx = n_buf
        else:
            estimator = self.initialize_filter(measurements_df.iloc[0], dt_mean)
            start_idx = 1

        # Ownship covariance (constant for now)
        ownship_pos_std = np.array([1.0, 1.0, 2.0])
        ownship_att_std = np.array([0.01, 0.01, 0.02])
        ownship_cov = np.diag(np.concatenate([ownship_pos_std**2, ownship_att_std**2]))

        for i in range(start_idx, len(measurements_df)):
            row = measurements_df.iloc[i]

            dt = dt_values[i - 1] if i > 0 else dt_mean
            estimator.dt = dt

            estimator.predict()

            ownship_pos = np.array([row['ownship_north_m'], row['ownship_east_m'], row['ownship_down_m']])
            ownship_att = np.array([row['ownship_roll_rad'], row['ownship_pitch_rad'], row['ownship_yaw_rad']])
            measurement = np.array([row['azimuth_rad'], row['elevation_rad'], row['range_m']])

            estimator.update(measurement, ownship_pos, ownship_att, ownship_cov)

            yield estimator, row
    


def main():
    """Main function."""
    parser = argparse.ArgumentParser(description='UKF-based intruder tracking from vision measurements')
    
    parser.add_argument('--input', '-i', required=True,
                      help='Input CSV file with vision measurements')
    parser.add_argument('--output', '-o', 
                      help='Output CSV file for tracking results')
    # Noise parameters
    parser.add_argument('--process-acceleration-noise-ftps2', type=float, default=10.0,
                      help='Process noise std — acceleration (m/s^2), used by CV model')
    parser.add_argument('--process-jerk-noise-ftps3', type=float, default=1.0,
                      help='Process noise std — jerk (m/s^3), used by CA model')
    parser.add_argument('--azimuth-noise-rad', type=float, default=0.02,
                      help='Azimuth measurement noise std (radians)')
    parser.add_argument('--elevation-noise-rad', type=float, default=0.02, 
                      help='Elevation measurement noise std (radians)')
    parser.add_argument('--range-noise-m', type=float, default=15.24,
                      help='Range measurement noise std (metres)')
    parser.add_argument('--estimator', type=str, default='cv',
                      choices=list(ESTIMATOR_CLASSES.keys()),
                      help='Estimator model to use (default: cv)')
    parser.add_argument('--init-window', type=int, default=3,
                      help='Number of measurements to buffer for initial velocity estimation (default: 3, min 2)')
    
    args = parser.parse_args()
    
    # Validate input
    if not os.path.exists(args.input):
        print(f"Error: Input file '{args.input}' not found")
        sys.exit(1)
        
    # Set up measurement noise
    measurement_noise = {
        'azimuth_rad': args.azimuth_noise_rad,
        'elevation_rad': args.elevation_noise_rad,  
        'range_m': args.range_noise_m
    }
    
    try:
        # Select process noise based on estimator model
        if args.estimator in ('ca', 'cab'):
            process_noise = args.process_jerk_noise_ftps3
        else:
            process_noise = args.process_acceleration_noise_ftps2

        # Create tracker
        tracker = VisionTracker(
            process_noise_std=process_noise,
            measurement_noise_std=measurement_noise,
            estimator_class=ESTIMATOR_CLASSES[args.estimator],
            init_window=args.init_window,
        )
        
        # Load measurements
        measurements_df = tracker.load_measurements(args.input)
        if measurements_df is None:
            sys.exit(1)
        
        # Run tracking  
        results_df = tracker.run_tracking(measurements_df, args.output)
        
        print("Tracking completed successfully!")
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
