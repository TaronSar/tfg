#!/usr/bin/env python3
"""
Unscented Kalman Filter with Constant Acceleration motion model for intruder tracking.
"""

import numpy as np

from .unscented_kalman_filter_base import UnscentedKalmanFilterBase


class UnscentedKalmanFilter_CA(UnscentedKalmanFilterBase):
    """
    Unscented Kalman Filter with Constant Acceleration motion model.

    State vector: [north, east, down, vn, ve, vd, an, ae, ad]
                  (position, velocity, and acceleration in NED frame)
    Measurements: [azimuth, elevation, range] from ownship aircraft camera
    """

    DIM_X = 9

    def __init__(self, dt, alpha=1e-3, beta=2.0, kappa=None):
        super().__init__(9, 3, dt, alpha, beta, kappa)

    def initialize(self, initial_position, dt, process_noise_std, measurement_noise_std,
                   position_variance=1000.0, initial_velocity=None,
                   velocity_variance=100.0, acceleration_variance=1.0):
        self.dt = dt

        vel = initial_velocity if initial_velocity is not None else np.zeros(3)
        self.x = np.array([*initial_position, *vel, 0.0, 0.0, 0.0])

        pv = np.broadcast_to(position_variance, 3)
        vv = np.broadcast_to(velocity_variance, 3)
        av = np.broadcast_to(acceleration_variance, 3)
        self.P = np.diag(np.concatenate([pv, vv, av]))

        # Process noise covariance (constant acceleration model, driven by jerk)
        # For each axis the continuous-time noise is:
        #   q_axis * [[dt^5/20, dt^4/8, dt^3/6],
        #             [dt^4/8,  dt^3/3, dt^2/2],
        #             [dt^3/6,  dt^2/2, dt    ]]
        q = process_noise_std
        d = dt
        Q_block = np.array([
            [d**5 / 20, d**4 / 8, d**3 / 6],
            [d**4 / 8,  d**3 / 3, d**2 / 2],
            [d**3 / 6,  d**2 / 2, d       ],
        ]) * q**2

        self.Q = np.zeros((9, 9))
        for axis in range(3):  # north, east, down
            idx = [axis, axis + 3, axis + 6]  # pos, vel, acc for this axis
            for i, ii in enumerate(idx):
                for j, jj in enumerate(idx):
                    self.Q[ii, jj] = Q_block[i, j]

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
            'intruder_an_ftps2': self.x[6],
            'intruder_ae_ftps2': self.x[7],
            'intruder_ad_ftps2': self.x[8],
        }

    def propagate_batch(self, taus):
        pos = self.x[:3].copy()
        vel = self.x[3:6].copy()
        acc = self.x[6:9].copy()
        P_full = self.P
        results = []
        for tau in taus:
            p = pos + vel * tau + 0.5 * acc * tau**2
            P_pp = P_full[0:3, 0:3]
            P_pv = P_full[0:3, 3:6]
            P_pa = P_full[0:3, 6:9]
            P_vp = P_full[3:6, 0:3]
            P_vv = P_full[3:6, 3:6]
            P_va = P_full[3:6, 6:9]
            P_ap = P_full[6:9, 0:3]
            P_av = P_full[6:9, 3:6]
            P_aa = P_full[6:9, 6:9]
            t = tau
            t2 = t * t
            ht2 = 0.5 * t2
            P_pos = (P_pp
                     + t * (P_pv + P_vp)
                     + ht2 * (P_pa + P_ap)
                     + t2 * P_vv
                     + t * ht2 * (P_va + P_av)
                     + ht2 * ht2 * P_aa)
            results.append((p, P_pos))
        return results

    def predict(self):
        """Prediction step using constant acceleration motion model."""
        self.sigma_points = self.generate_sigma_points(self.x, self.P)
        if self.sigma_points is None:
            return

        dt = self.dt
        half_dt2 = 0.5 * dt * dt

        for i in range(self.n_sigma):
            s = self.sigma_points[i]
            # Constant acceleration model:
            #   p_{k+1} = p_k + v_k*dt + 0.5*a_k*dt^2
            #   v_{k+1} = v_k + a_k*dt
            #   a_{k+1} = a_k
            s[0] += s[3] * dt + s[6] * half_dt2  # north
            s[1] += s[4] * dt + s[7] * half_dt2  # east
            s[2] += s[5] * dt + s[8] * half_dt2  # down
            s[3] += s[6] * dt                     # vn
            s[4] += s[7] * dt                     # ve
            s[5] += s[8] * dt                     # vd
            # Acceleration remains constant

        # Predicted state mean
        self.x = np.sum(self.Wm[:, np.newaxis] * self.sigma_points, axis=0)

        # Predicted covariance
        self.P = self.Q.copy()
        for i in range(self.n_sigma):
            y = self.sigma_points[i] - self.x
            self.P += self.Wc[i] * np.outer(y, y)

