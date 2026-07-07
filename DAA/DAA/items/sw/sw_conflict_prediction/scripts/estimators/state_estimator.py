#!/usr/bin/env python3
"""
Abstract base class for state estimators used in vision-based intruder tracking.
"""

import numpy as np
from abc import ABC, abstractmethod
from collections import namedtuple


CylinderDistanceResult = namedtuple(
    'CylinderDistanceResult',
    ['min_cyldist', 'idx_cpa'],
)
"""Output of :meth:`StateEstimator.min_1sigma_cylinder_distance`.

Fields:
    min_cyldist: Minimum 1-sigma cylinder distance over the sweep
        (dimensionless).
    idx_cpa:     Sample index of the Closest Point of Approach — the
                 trajectory sample that minimises the cylinder
                 distance. The caller can derive tCPA, the Euclidean
                 range, etc. from this index and the trajectory inputs.
"""


class StateEstimator(ABC):
    """
    Abstract base class for state estimators used in vision-based intruder tracking.

    All estimators must track at minimum position [north, east, down] and
    velocity [vn, ve, vd] of the intruder in NED frame. Subclasses may track
    additional states (e.g. acceleration) depending on the motion model.
    """

    def __init__(self, dim_x, dim_z, dt):
        """
        Args:
            dim_x: Dimension of state vector
            dim_z: Dimension of measurement vector
            dt: Time step in seconds
        """
        self.dim_x = dim_x
        self.dim_z = dim_z
        self.dt = dt
        # Pre-allocate state and covariance so methods that introspect
        # the state (e.g. get_state_dict, load_state_from_row) work on a
        # freshly-constructed estimator, before initialize() is called.
        # Subclasses that expose x/P as read-only properties (e.g. the
        # embedded DLL wrapper) override these and the assignment is
        # skipped.
        try:
            self.x = np.zeros(dim_x)
            self.P = np.eye(dim_x)
        except AttributeError:
            pass
        self.Q = np.zeros((dim_x, dim_x))
        self.R = np.eye(dim_z)

    @abstractmethod
    def initialize(self, initial_position, dt, process_noise_std, measurement_noise_std,
                   position_variance=1000.0, initial_velocity=None,
                   velocity_variance=100.0, acceleration_variance=1.0):
        """
        Initialize the estimator state and noise matrices.

        Args:
            initial_position: Initial intruder position [north, east, down] in feet
            dt: Mean time step in seconds
            process_noise_std: Process noise standard deviation
            measurement_noise_std: Dict with keys 'azimuth_rad', 'elevation_rad', 'range_ft'
            position_variance: Initial position variance (ft^2). Scalar or
                array-like of length 3 [north, east, down].
            initial_velocity: Optional initial velocity [vn, ve, vd] in ft/s.
                Defaults to zero velocity.
            velocity_variance: Initial velocity variance (ft/s)^2. Scalar or
                array-like of length 3 [vn, ve, vd].
            acceleration_variance: Initial acceleration variance (ft/s^2)^2.
                Scalar or array-like of length 3. Only used by models
                that track acceleration (CA, CAB).
        """

    @abstractmethod
    def predict(self):
        """Perform the prediction (time update) step."""

    @abstractmethod
    def update(self, z, ownship_pos, ownship_attitude, ownship_cov):
        """
        Perform the measurement update step.

        Args:
            z: Measurement vector [azimuth, elevation, range]
            ownship_pos: Ownship position [north, east, down] in feet
            ownship_attitude: Ownship attitude [roll, pitch, yaw] in radians
            ownship_cov: 6x6 ownship covariance matrix [pos, attitude]
        """

    @abstractmethod
    def get_state_dict(self):
        """Return dict mapping output column names to current state values."""

    @classmethod
    @abstractmethod
    def reconstruct_covariance(cls, row):
        """Reconstruct the full symmetric covariance matrix from a CSV row.

        Args:
            row: A pandas Series (or dict) with keys 'P_{i}{j}' for the upper triangle.

        Returns:
            Full dim_x × dim_x symmetric covariance matrix as np.ndarray.
        """

    def load_state_from_row(self, row):
        """Load state vector and covariance from a CSV row (or dict).

        The row must contain all columns produced by :meth:`get_state_dict`
        plus upper-triangle covariance entries ``P_{i}{j}``.
        """
        # Build x from the state-dict column order (keys match get_state_dict)
        keys = list(self.get_state_dict().keys())
        self.x = np.array([row[k] for k in keys], dtype=np.float64)
        self.P = type(self).reconstruct_covariance(row)

    @abstractmethod
    def propagate_batch(self, taus):
        """Propagate position and position covariance for a sequence of lookahead times.

        Uses the estimator's internal state (x, P) directly.

        Each estimator applies its own motion model.  Estimators with expensive
        numerical integration (e.g. CAB) reuse intermediate state across
        consecutive taus for efficiency and accuracy.

        Args:
            taus: Iterable of lookahead times in *ascending* order.

        Returns:
            List of (position, P_pos) tuples.
              - position: np.ndarray [north, east, down].
              - P_pos: 3×3 position covariance matrix.
        """

    def min_1sigma_cylinder_distance(
        self, own_traj, int_pos, int_cov, cyl_h, cyl_d,
    ):
        """Minimum 1-sigma cylinder distance along an ownship trajectory.

        Operates on a caller-supplied pre-computed intruder propagation
        (``int_pos`` / ``int_cov``).  Keeping the propagation outside this
        method allows the caller to reuse it when evaluating multiple
        candidate ownship trajectories against the same intruder state.
        This mirrors the C++ API.

        Args:
            own_traj: Array-like (N, 3) of ownship NED positions (ft).
            int_pos:  Array-like (N, 3) of propagated intruder positions
                      (ft) — typically obtained from
                      :meth:`propagate_batch`.
            int_cov:  Array-like (N, 3, 3) of propagated intruder
                      position covariances (ft^2).
            cyl_h:    Protection cylinder height (ft).
            cyl_d:    Protection cylinder diameter (ft).

        Returns:
            :class:`CylinderDistanceResult` with fields
            ``(min_cyldist, idx_cpa)``.
        """
        half_h = cyl_h / 2.0
        radius = cyl_d / 2.0

        own_traj = np.asarray(own_traj, dtype=np.float64)
        int_pos = np.asarray(int_pos, dtype=np.float64)
        int_cov = np.asarray(int_cov, dtype=np.float64)
        N = own_traj.shape[0]
        if own_traj.shape != (N, 3):
            raise ValueError(
                f"own_traj shape {own_traj.shape} does not match (N={N}, 3)"
            )
        if int_pos.shape != (N, 3):
            raise ValueError(
                f"int_pos shape {int_pos.shape} does not match (N={N}, 3)"
            )
        if int_cov.shape != (N, 3, 3):
            raise ValueError(
                f"int_cov shape {int_cov.shape} does not match (N={N}, 3, 3)"
            )

        min_dist = np.inf
        idx_cpa = 0
        for i, (own_future, future_int_pos, P_pos) in enumerate(
                zip(own_traj, int_pos, int_cov)):
            rel = future_int_pos - own_future

            horiz = np.sqrt(rel[0]**2 + rel[1]**2)
            if horiz > 1e-6:
                u = np.array([rel[0], rel[1]]) / horiz
            else:
                u = np.array([1.0, 0.0])
            rad_std = np.sqrt(max(u @ P_pos[:2, :2] @ u, 0.0))
            down_std = np.sqrt(max(P_pos[2, 2], 0.0))

            d_xy = horiz / (radius + rad_std)
            d_z = abs(rel[2]) / (half_h + down_std)
            d = max(d_xy, d_z)
            if d < min_dist:
                min_dist = d
                idx_cpa = i

        return CylinderDistanceResult(
            min_cyldist=float(min_dist), idx_cpa=int(idx_cpa),
        )


def get_estimator_classes():
    """Return the estimator registry mapping short names to classes.

    Imports are deferred to avoid circular dependencies (the subclass
    modules import StateEstimator from this file).
    """
    from .unscented_kalman_filter_cv import UnscentedKalmanFilter_CV
    from .unscented_kalman_filter_ca import UnscentedKalmanFilter_CA
    from .unscented_kalman_filter_cab import UnscentedKalmanFilter_CAB

    return {
        'cv': UnscentedKalmanFilter_CV,
        'ca': UnscentedKalmanFilter_CA,
        'cab': UnscentedKalmanFilter_CAB,
    }
