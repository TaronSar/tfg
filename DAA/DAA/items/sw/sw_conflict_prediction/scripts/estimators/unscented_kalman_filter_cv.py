#!/usr/bin/env python3
"""
Unscented Kalman Filter with Constant Velocity motion model for intruder tracking.
"""

import numpy as np

from .unscented_kalman_filter_base import UnscentedKalmanFilterBase


class UnscentedKalmanFilter_CV(UnscentedKalmanFilterBase):
    """
    Unscented Kalman Filter with Constant Velocity motion model.

    State vector: [north, east, down, vn, ve, vd] (position and velocity in NED frame)
    Measurements: [azimuth, elevation, range] from ownship aircraft camera
    """

    DIM_X = 6

    def __init__(self, dt, alpha=1e-3, beta=2.0, kappa=None):
        super().__init__(6, 3, dt, alpha, beta, kappa)

    def initialize(self, initial_position, dt, process_noise_std, measurement_noise_std,
                   position_variance=1000.0, initial_velocity=None,
                   velocity_variance=100.0, acceleration_variance=1.0):
        self.dt = dt

        vel = initial_velocity if initial_velocity is not None else np.zeros(3)
        self.x = np.array([*initial_position, *vel])

        pv = np.broadcast_to(position_variance, 3)
        vv = np.broadcast_to(velocity_variance, 3)
        self.P = np.diag(np.concatenate([pv, vv]))

        # Process noise covariance (constant velocity model)
        q = process_noise_std
        self.Q = np.array([
            [dt**4/4, 0, 0, dt**3/2, 0, 0],
            [0, dt**4/4, 0, 0, dt**3/2, 0],
            [0, 0, dt**4/4, 0, 0, dt**3/2],
            [dt**3/2, 0, 0, dt**2, 0, 0],
            [0, dt**3/2, 0, 0, dt**2, 0],
            [0, 0, dt**3/2, 0, 0, dt**2]
        ]) * q**2

        # Measurement noise covariance
        self.R = np.diag([
            measurement_noise_std['azimuth_rad']**2,
            measurement_noise_std['elevation_rad']**2,
            measurement_noise_std['range_ft']**2
        ])

    def get_state_dict(self):
        return {
            'intruder_north_ft': self.x[0],
            'intruder_east_ft': self.x[1],
            'intruder_down_ft': self.x[2],
            'intruder_vn_ftps': self.x[3],
            'intruder_ve_ftps': self.x[4],
            'intruder_vd_ftps': self.x[5],
        }

    def propagate_batch(self, taus):
        pos = self.x[:3].copy()
        vel = self.x[3:6].copy()
        P_full = self.P
        results = []
        for tau in taus:
            p = pos + vel * tau
            P_pp = P_full[:3, :3]
            P_pv = P_full[:3, 3:]
            P_vp = P_full[3:, :3]
            P_vv = P_full[3:, 3:]
            P_pos = P_pp + tau * (P_pv + P_vp) + tau**2 * P_vv
            results.append((p, P_pos))
        return results

    def predict(self):
        """Prediction step using constant velocity motion model."""
        # Generate sigma points
        self.sigma_points = self.generate_sigma_points(self.x, self.P)
        if self.sigma_points is None:
            return

        # Propagate sigma points through motion model
        for i in range(self.n_sigma):
            # Constant velocity model: x_k+1 = x_k + v_k * dt
            self.sigma_points[i, 0] += self.sigma_points[i, 3] * self.dt  # north
            self.sigma_points[i, 1] += self.sigma_points[i, 4] * self.dt  # east
            self.sigma_points[i, 2] += self.sigma_points[i, 5] * self.dt  # down
            # Velocity remains constant: v_k+1 = v_k

        # Compute predicted state mean
        self.x = np.sum(self.Wm[:, np.newaxis] * self.sigma_points, axis=0)

        # Compute predicted covariance
        self.P = self.Q.copy()
        for i in range(self.n_sigma):
            y = self.sigma_points[i] - self.x
            self.P += self.Wc[i] * np.outer(y, y)
