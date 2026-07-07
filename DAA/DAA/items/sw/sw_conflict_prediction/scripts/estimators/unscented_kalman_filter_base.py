#!/usr/bin/env python3
"""
Base class for all Unscented Kalman Filter motion model variants.

Collects the UKF machinery shared by every motion model (CV, CA, CAB, …):
  - sigma-point generation & weight computation
  - measurement function  (NED → azimuth / elevation / range)
  - ownship-induced noise via mini Unscented Transform
  - the full UKF measurement-update step
  - covariance reconstruction from a CSV row

Subclasses only need to implement the model-specific pieces:
  initialize, predict, get_state_dict, propagate_batch.
"""

import numpy as np

from .state_estimator import StateEstimator


class UnscentedKalmanFilterBase(StateEstimator):
    """
    Base Unscented Kalman Filter.

    Subclasses must set the class attribute ``DIM_X`` (state dimension) and
    implement:  ``initialize``, ``predict``, ``get_state_dict``,
    ``propagate_batch``.
    """

    # Subclasses MUST override with actual state dimension (e.g. 6, 9).
    DIM_X: int = NotImplemented

    def __init__(self, dim_x, dim_z, dt, alpha=1e-3, beta=2.0, kappa=None):
        super().__init__(dim_x, dim_z, dt)

        # UKF tuning parameters
        self.alpha = alpha
        self.beta = beta
        self.kappa = kappa if kappa is not None else 3 - dim_x

        # Derived UKF parameters
        self.lambda_ = self.alpha**2 * (dim_x + self.kappa) - dim_x
        self.n_sigma = 2 * dim_x + 1

        # Sigma point weights
        self.Wm = np.zeros(self.n_sigma)  # Mean weights
        self.Wc = np.zeros(self.n_sigma)  # Covariance weights

        self.Wm[0] = self.lambda_ / (dim_x + self.lambda_)
        self.Wc[0] = self.lambda_ / (dim_x + self.lambda_) + (1 - self.alpha**2 + self.beta)

        for i in range(1, self.n_sigma):
            self.Wm[i] = 1.0 / (2 * (dim_x + self.lambda_))
            self.Wc[i] = 1.0 / (2 * (dim_x + self.lambda_))

        # Sigma points storage
        self.sigma_points = np.zeros((self.n_sigma, dim_x))
        self.sigma_z = np.zeros((self.n_sigma, dim_z))

    # ------------------------------------------------------------------
    # Sigma-point generation
    # ------------------------------------------------------------------

    def generate_sigma_points(self, x, P, lambda_val=None):
        """Generate sigma points around state estimate.

        Args:
            x: State vector
            P: Covariance matrix
            lambda_val: Optional lambda parameter. If None, uses self.lambda_
        """
        dim = len(x)
        n_sig = 2 * dim + 1

        if lambda_val is None:
            lambda_val = self.lambda_
            n_sig = self.n_sigma

        sigma_points = np.zeros((n_sig, dim))
        sigma_points[0] = x

        try:
            sqrt_matrix = np.linalg.cholesky((dim + lambda_val) * P).T
        except np.linalg.LinAlgError as exc:
            print(
                'Warning: UKF sigma-point generation failed '
                '(Cholesky decomposition). Covariance may be '
                f'non-positive-definite; skipping this step. ({exc})'
            )
            return None

        for i in range(dim):
            sigma_points[i + 1] = x + sqrt_matrix[i]
            sigma_points[i + 1 + dim] = x - sqrt_matrix[i]

        return sigma_points

    # ------------------------------------------------------------------
    # Angle-wrapping helper
    # ------------------------------------------------------------------

    @staticmethod
    def _wrap_angle(a):
        """Wrap angle(s) to the range (-pi, pi]."""
        return (a + np.pi) % (2 * np.pi) - np.pi

    # ------------------------------------------------------------------
    # Measurement model (common to all motion models)
    # ------------------------------------------------------------------

    def measurement_function(self, state_sigma, ownship_pos, ownship_attitude):
        """
        Convert intruder state to expected measurements.

        Args:
            state_sigma: Intruder state (first 3 elements are position in NED)
            ownship_pos: Ownship position [north, east, down] in feet
            ownship_attitude: Ownship attitude [roll, pitch, yaw] in radians

        Returns:
            Expected measurements [azimuth, elevation, range]
        """
        intruder_pos = state_sigma[:3]
        rel_ned = intruder_pos - ownship_pos

        roll, pitch, yaw = ownship_attitude
        cos_roll, sin_roll = np.cos(roll), np.sin(roll)
        cos_pitch, sin_pitch = np.cos(pitch), np.sin(pitch)
        cos_yaw, sin_yaw = np.cos(yaw), np.sin(yaw)

        R_yaw = np.array([[ cos_yaw, sin_yaw, 0],
                           [-sin_yaw, cos_yaw, 0],
                           [       0,       0, 1]])
        R_pitch = np.array([[cos_pitch, 0, -sin_pitch],
                            [        0, 1,          0],
                            [sin_pitch, 0,  cos_pitch]])
        R_roll = np.array([[1,         0,        0],
                           [0,  cos_roll, sin_roll],
                           [0, -sin_roll, cos_roll]])

        body = R_roll @ R_pitch @ R_yaw @ rel_ned
        x_body, y_body, z_body = body

        azimuth = np.arctan2(y_body, x_body)
        horizontal_distance = np.sqrt(x_body**2 + y_body**2)
        elevation = np.arctan2(-z_body, horizontal_distance)
        range_dist = np.sqrt(x_body**2 + y_body**2 + z_body**2)

        return np.array([azimuth, elevation, range_dist])

    # ------------------------------------------------------------------
    # Ownship-induced measurement noise
    # ------------------------------------------------------------------

    def compute_ownship_induced_noise(self, intruder_state, ownship_pos, ownship_att, ownship_cov):
        """
        Calculates the measurement covariance induced by ownship uncertainty.
        Uses a mini-Unscented Transform on the ownship state.
        """
        dim_ownship = 6  # 3 pos + 3 att
        # Use a kappa appropriate for the ownship dimension, not self.kappa
        # which is tuned for the (possibly larger) state dimension.
        kappa_ownship = 3 - dim_ownship
        lambda_ownship = self.alpha**2 * (dim_ownship + kappa_ownship) - dim_ownship

        ownship_mean = np.concatenate([ownship_pos, ownship_att])
        ownship_sigmas = self.generate_sigma_points(ownship_mean, ownship_cov, lambda_ownship)
        if ownship_sigmas is None:
            return None
        n_sig_ownship = len(ownship_sigmas)

        Wm_ownship = np.zeros(n_sig_ownship)
        Wc_ownship = np.zeros(n_sig_ownship)
        Wm_ownship[0] = lambda_ownship / (dim_ownship + lambda_ownship)
        Wc_ownship[0] = lambda_ownship / (dim_ownship + lambda_ownship) + (1 - self.alpha**2 + self.beta)
        for i in range(1, n_sig_ownship):
            weight = 1.0 / (2 * (dim_ownship + lambda_ownship))
            Wm_ownship[i] = weight
            Wc_ownship[i] = weight

        z_ownship_sigmas = np.zeros((n_sig_ownship, self.dim_z))
        for i in range(n_sig_ownship):
            s_pos = ownship_sigmas[i, :3]
            s_att = ownship_sigmas[i, 3:]
            z_ownship_sigmas[i] = self.measurement_function(intruder_state, s_pos, s_att)

        # Azimuth mean via reference-point method (safe with negative weights).
        # Use the central sigma point as reference so that the dangerous
        # W_m[0] is multiplied by wrap(theta_0 - theta_0) = 0.
        z_mean = np.sum(Wm_ownship[:, np.newaxis] * z_ownship_sigmas, axis=0)
        az_ref = z_ownship_sigmas[0, 0]
        z_mean[0] = az_ref + np.sum(
            Wm_ownship * self._wrap_angle(z_ownship_sigmas[:, 0] - az_ref))

        R_induced = np.zeros((self.dim_z, self.dim_z))
        for i in range(n_sig_ownship):
            y = z_ownship_sigmas[i] - z_mean
            y[0] = self._wrap_angle(y[0])
            R_induced += Wc_ownship[i] * np.outer(y, y)

        return R_induced

    # ------------------------------------------------------------------
    # UKF measurement update (common to all motion models)
    # ------------------------------------------------------------------

    def update(self, z, ownship_pos, ownship_attitude, ownship_cov):
        """
        Update step accounting for ownship covariance.

        Args:
            z: Measurement vector [azimuth, elevation, range]
            ownship_pos: Ownship position [north, east, down] in feet
            ownship_attitude: Ownship attitude [roll, pitch, yaw] in radians
            ownship_cov: 6×6 ownship covariance matrix [pos, attitude]
        """
        R_total = self.R.copy()

        R_geo = self.compute_ownship_induced_noise(
            self.x, ownship_pos, ownship_attitude, ownship_cov)
        if R_geo is None:
            return
        R_total += R_geo

        self.sigma_points = self.generate_sigma_points(self.x, self.P)
        if self.sigma_points is None:
            return

        for i in range(self.n_sigma):
            self.sigma_z[i] = self.measurement_function(
                self.sigma_points[i], ownship_pos, ownship_attitude)

        # Azimuth (index 0) is a circular quantity that wraps at ±π.
        # Use the reference-point method: deviations from the central sigma
        # point are wrapped before weighting, so the large negative W_m[0]
        # is multiplied by wrap(0) = 0 and cannot flip the mean by 180°.
        z_pred = np.sum(self.Wm[:, np.newaxis] * self.sigma_z, axis=0)
        az_ref = self.sigma_z[0, 0]
        z_pred[0] = az_ref + np.sum(
            self.Wm * self._wrap_angle(self.sigma_z[:, 0] - az_ref))

        Pz = R_total.copy()
        for i in range(self.n_sigma):
            y = self.sigma_z[i] - z_pred
            y[0] = self._wrap_angle(y[0])
            Pz += self.Wc[i] * np.outer(y, y)

        Pxz = np.zeros((self.dim_x, self.dim_z))
        for i in range(self.n_sigma):
            dx = self.sigma_points[i] - self.x
            dz = self.sigma_z[i] - z_pred
            dz[0] = self._wrap_angle(dz[0])
            Pxz += self.Wc[i] * np.outer(dx, dz)

        try:
            K = np.linalg.solve(Pz.T, Pxz.T).T
        except np.linalg.LinAlgError:
            print("Warning: Skipping UKF update — singular covariance matrix")
            return

        innovation = z - z_pred
        innovation[0] = self._wrap_angle(innovation[0])

        self.x = self.x + K @ innovation
        self.P = self.P - K @ Pz @ K.T
        # Force symmetry — floating-point drift in the update can make P
        # slightly asymmetric, which would crash the Cholesky decomposition.
        self.P = 0.5 * (self.P + self.P.T)

    # ------------------------------------------------------------------
    # Covariance serialisation helper
    # ------------------------------------------------------------------

    @classmethod
    def reconstruct_covariance(cls, row):
        """Reconstruct the full symmetric covariance from a CSV row."""
        dim = cls.DIM_X
        P = np.zeros((dim, dim))
        for i in range(dim):
            for j in range(i, dim):
                val = row[f'P_{i}{j}']
                P[i, j] = val
                P[j, i] = val
        return P
