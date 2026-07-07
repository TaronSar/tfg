#!/usr/bin/env python3
"""
Unscented Kalman Filter with Constant Acceleration in the velocity-aligned (body) frame.

Unlike the CA model which assumes constant acceleration in NED, this model assumes
constant acceleration in a frame aligned with the horizontal velocity direction:
  - Tangential: along the horizontal velocity (speed change)
  - Normal: perpendicular to horizontal velocity in the horizontal plane (turning)
  - Vertical: NED down axis (climb/descent rate change)

This better captures aircraft dynamics during maneuvers such as constant-rate turns,
where the NED acceleration components change continuously but the body-frame
acceleration is nearly constant.
"""

import numpy as np

from .unscented_kalman_filter_base import UnscentedKalmanFilterBase


class UnscentedKalmanFilter_CAB(UnscentedKalmanFilterBase):
    """
    Unscented Kalman Filter with Constant Acceleration in the Body frame.

    State vector: [north, east, down, vn, ve, vd, a_tangential, a_normal, a_vertical]
    Measurements: [azimuth, elevation, range] from ownship aircraft camera

    The body frame is defined by the horizontal velocity direction:
      - Tangential axis: along horizontal velocity  (cos ψ, sin ψ, 0)
      - Normal axis: perpendicular in horizontal    (-sin ψ, cos ψ, 0)
      - Vertical axis: NED down                     (0, 0, 1)
    where ψ = atan2(ve, vn) is the heading angle.
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

        # Process noise: random walk on body-frame acceleration (driven by jerk)
        q = process_noise_std
        self.Q = np.zeros((9, 9))
        self.Q[6, 6] = q**2 * dt
        self.Q[7, 7] = q**2 * dt
        self.Q[8, 8] = q**2 * dt

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
            'intruder_a_tangential_ftps2': self.x[6],
            'intruder_a_normal_ftps2': self.x[7],
            'intruder_a_vertical_ftps2': self.x[8],
        }

    # ------------------------------------------------------------------
    # Velocity-frame helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _body_to_ned_accel(vel, a_body):
        """Convert body-frame acceleration to NED given current velocity."""
        vh = np.sqrt(vel[0]**2 + vel[1]**2)
        if vh > 1e-6:
            cp, sp = vel[0] / vh, vel[1] / vh
        else:
            cp, sp = 1.0, 0.0
        return np.array([
            a_body[0] * cp - a_body[1] * sp,
            a_body[0] * sp + a_body[1] * cp,
            a_body[2]
        ])

    @staticmethod
    def _integrate_position(pos, vel, a_body, tau, P=None):
        """Integrate position forward assuming constant body-frame acceleration.

        Uses Euler integration with ~10 steps per second to capture
        heading changes during turns.  Optionally propagates the full
        9×9 covariance through each step using the local Jacobian.

        Returns (position, velocity, P_propagated) tuple.
        P_propagated is None when the input P is None.
        """
        n_steps = max(int(abs(tau) * 10), 1)
        dt = tau / n_steps
        p = pos.copy()
        v = vel.copy()
        P_cur = P.copy() if P is not None else None

        # Jacobian heading management – see note below on the blend ramp.
        #
        # When horizontal speed vh drops below VH_THRESHOLD the heading
        # ψ = atan2(ve, vn) becomes indeterminate.  Both the da/dv
        # coupling term and R(ψ) depend on (cos ψ, sin ψ) and would
        # oscillate wildly, causing covariance jitter.
        #
        # We keep a "frozen" heading (cp_jac, sp_jac) that tracks the
        # live heading above the threshold.  Below VH_BLEND (half the
        # threshold) the Jacobian uses the frozen heading exclusively.
        # In between we blend linearly so that the Jacobian transitions
        # smoothly and adjacent frames don't see a discontinuity.
        VH_THRESHOLD = 50.0  # ft/s – full-live heading above this
        VH_BLEND     = 20.0  # ft/s – fully-frozen heading below this

        vh0 = np.sqrt(vel[0]**2 + vel[1]**2)
        if vh0 > VH_BLEND:
            cp_jac, sp_jac = vel[0] / vh0, vel[1] / vh0
        else:
            cp_jac, sp_jac = 1.0, 0.0

        for _ in range(n_steps):
            vh2 = v[0]**2 + v[1]**2
            vh = np.sqrt(vh2)

            if vh > 1e-6:
                cp, sp = v[0] / vh, v[1] / vh
            else:
                cp, sp = 1.0, 0.0

            # Heun (velocity-midpoint) integration
            a1 = np.array([
                a_body[0] * cp - a_body[1] * sp,
                a_body[0] * sp + a_body[1] * cp,
                a_body[2]
            ])
            v_pred = v + a1 * dt
            vh_p = np.sqrt(v_pred[0]**2 + v_pred[1]**2)
            if vh_p > 1e-6:
                cp2, sp2 = v_pred[0] / vh_p, v_pred[1] / vh_p
            else:
                cp2, sp2 = cp, sp
            a2 = np.array([
                a_body[0] * cp2 - a_body[1] * sp2,
                a_body[0] * sp2 + a_body[1] * cp2,
                a_body[2]
            ])
            a_avg = 0.5 * (a1 + a2)

            p += v * dt + 0.5 * a_avg * dt * dt
            v += a_avg * dt

            if P_cur is not None:
                # Update frozen heading while speed is meaningful
                if vh > VH_BLEND:
                    cp_jac, sp_jac = cp, sp

                # Blend factor: 1 = use live (cp, sp),  0 = use frozen
                if vh >= VH_THRESHOLD:
                    alpha_blend = 1.0
                elif vh <= VH_BLEND:
                    alpha_blend = 0.0
                else:
                    alpha_blend = (vh - VH_BLEND) / (VH_THRESHOLD - VH_BLEND)

                cp_eff = alpha_blend * cp + (1.0 - alpha_blend) * cp_jac
                sp_eff = alpha_blend * sp + (1.0 - alpha_blend) * sp_jac

                a_N_eff = a_body[0] * cp_eff - a_body[1] * sp_eff
                a_E_eff = a_body[0] * sp_eff + a_body[1] * cp_eff

                # ∂a_NED/∂v (3×3) – scales with alpha_blend so it
                # ramps to zero smoothly as vh enters the blend zone.
                if vh > VH_BLEND:
                    da_dv = alpha_blend * np.array([
                        [ a_E_eff * v[1] / vh2, -a_E_eff * v[0] / vh2, 0.0],
                        [-a_N_eff * v[1] / vh2,  a_N_eff * v[0] / vh2, 0.0],
                        [0.0,                    0.0,                   0.0]
                    ])
                else:
                    da_dv = np.zeros((3, 3))

                # R(ψ): rotation from body to NED (blended heading)
                R_psi = np.array([
                    [cp_eff, -sp_eff, 0.0],
                    [sp_eff,  cp_eff, 0.0],
                    [0.0,     0.0,    1.0]
                ])

                # 9×9 step Jacobian
                F = np.eye(9)
                F[0:3, 3:6] = np.eye(3) * dt + 0.5 * dt * dt * da_dv
                F[0:3, 6:9] = 0.5 * dt * dt * R_psi
                F[3:6, 3:6] = np.eye(3) + dt * da_dv
                F[3:6, 6:9] = dt * R_psi

                P_cur = F @ P_cur @ F.T

        return p, v, P_cur

    # ------------------------------------------------------------------
    # Propagation interface
    # ------------------------------------------------------------------

    def propagate_batch(self, taus):
        """Incrementally integrate position and propagate covariance.

        Position and covariance are propagated together through each Euler
        step, using the local Jacobian at each step.  This correctly
        captures how uncertainty evolves along a curved (turning) trajectory.

        Note: the analytical 9×9 Jacobian (F) in _integrate_position is
        only used here for lookahead covariance propagation (collision
        avoidance).  The UKF predict/update cycle uses the Unscented
        Transform and does not rely on F.
        """
        pos = self.x[:3].copy()
        vel = self.x[3:6].copy()
        a_body = self.x[6:9].copy()
        results = []
        prev_tau = 0.0
        P_cur = self.P
        for tau in taus:
            delta = tau - prev_tau
            pos, vel, P_cur = self._integrate_position(pos, vel, a_body, delta, P_cur)
            P_pos = P_cur[0:3, 0:3]
            results.append((pos.copy(), P_pos))
            prev_tau = tau
        return results

    def predict(self):
        """Prediction step using constant body-frame acceleration model.

        Each sigma point is propagated through sub-stepped Euler integration
        (same rate as _integrate_position) so that the heading-dependent
        NED acceleration is re-evaluated at each sub-step.  A single-step
        Euler would "swing wide" during turns because it freezes a_NED at
        the initial heading for the entire dt.
        """
        self.sigma_points = self.generate_sigma_points(self.x, self.P)
        if self.sigma_points is None:
            return

        dt = self.dt
        n_sub = max(int(dt * 10), 1)
        h = dt / n_sub

        for i in range(self.n_sigma):
            s = self.sigma_points[i]
            for _ in range(n_sub):
                # Heun (velocity-midpoint) integration:
                # 1) Euler predictor for velocity
                a1 = self._body_to_ned_accel(s[3:6], s[6:9])
                v_pred = s[3:6] + a1 * h
                # 2) Corrector: acceleration from predicted velocity
                a2 = self._body_to_ned_accel(v_pred, s[6:9])
                # 3) Average acceleration
                a_avg = 0.5 * (a1 + a2)
                s[0:3] += s[3:6] * h + 0.5 * a_avg * h * h
                s[3:6] += a_avg * h

        self.x = np.sum(self.Wm[:, np.newaxis] * self.sigma_points, axis=0)

        self.P = self.Q.copy()
        for i in range(self.n_sigma):
            y = self.sigma_points[i] - self.x
            self.P += self.Wc[i] * np.outer(y, y)
