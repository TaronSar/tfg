// ---------------------------------------------------------------
// UKF_ctra.cpp — UKF_ctra non-inline method(s)
// ---------------------------------------------------------------
#include <Rmath.h>
#include <UKF_ctra.h>

namespace DAA
{

    UKF_ctra::UKF_ctra() :
            UKF_base(state_dim_, 3)
    {
    }

    void UKF_ctra::propagate_state(Real64* y, Real64 tau)
    {
        // Sub-step at ~10 Hz so the heading rotation through a turn is
        // resolved.  a_tang, omega and the vertical speed vd are held
        // constant across the horizon.
        Uint32 n_sub = static_cast<Uint32>(Rmath::fabsr(tau) * 10.0);
        if (n_sub < 1)
        {
            n_sub = 1;
        }
        const Real64 h = tau / static_cast<Real64>(n_sub);

        const Real64 a_t = y[idx_a_tang_];
        const Real64 w = y[idx_omega_];
        const Real64 vd = y[idx_vd_];

        for (Uint32 s = 0; s < n_sub; ++s)
        {
            const Real64 vn0 = y[idx_vn_];
            const Real64 ve0 = y[idx_ve_];
            const Real64 vh0 = Rmath::sqrtr(vn0 * vn0 + ve0 * ve0);

            // Heading from the horizontal velocity.  atan2r(0, 0) = 0 is a
            // benign, bounded choice at exactly zero speed: there is no
            // division by vh, so the velocity direction cannot be whipped
            // around as it can in the a_norm / vh body-frame model.
            const Real64 psi0 = Rmath::atan2r(ve0, vn0);

            // Tangentially accelerate the horizontal speed, but never let
            // it cross zero into negative: the (speed, heading) polar form
            // is sign-ambiguous — a negative speed is the same velocity as
            // a positive speed with the heading flipped 180 deg — so an
            // unclamped vh would flip the velocity direction the moment a
            // (poorly observable, possibly spurious) negative a_tang drives
            // it through zero.  A decelerating aircraft coasts to a stop,
            // it does not spontaneously reverse, so the speed is held at
            // zero instead; a genuine direction change is carried by omega
            // (heading rotation), not by a sign flip of the speed.
            Real64 vh1 = vh0 + a_t * h;
            if (vh1 < 0.0)
            {
                vh1 = 0.0;
            }
            const Real64 psi1 = psi0 + w * h;
            const Real64 vn1 = vh1 * Rmath::cosr(psi1);
            const Real64 ve1 = vh1 * Rmath::sinr(psi1);

            // Trapezoidal (velocity-midpoint) position update.
            y[idx_pn_] += 0.5 * (vn0 + vn1) * h;
            y[idx_pe_] += 0.5 * (ve0 + ve1) * h;
            y[idx_pd_] += vd * h;

            y[idx_vn_] = vn1;
            y[idx_ve_] = ve1;
            // vd, a_tang, omega unchanged
        }
    }

    void UKF_ctra::initialize(const Real64* initial_pos,
                              Real64 dt,
                              Real64 process_noise_std,
                              Real64 position_var,
                              const Real64* initial_vel,
                              Real64 velocity_var,
                              Real64 acceleration_var)
    {
        dt_ = dt;

        // State: [n, e, d, vn, ve, vd, a_tang, omega]
        x_[idx_pn_] = initial_pos[0];
        x_[idx_pe_] = initial_pos[1];
        x_[idx_pd_] = initial_pos[2];
        x_[idx_vn_] = initial_vel[0];
        x_[idx_ve_] = initial_vel[1];
        x_[idx_vd_] = initial_vel[2];
        x_[idx_a_tang_] = 0.0;
        x_[idx_omega_] = 0.0;

        // P = diag([position_var, velocity_var, acceleration_var]).  The
        // turn-rate (omega) entry is seeded with acceleration_var here so a
        // direct initialize() call is well-defined; the measurement
        // bootstrap path overwrites it with its dedicated turn-rate seed.
        P_.zeros();
        P_.get_ij(idx_pn_, idx_pn_) = position_var;
        P_.get_ij(idx_pe_, idx_pe_) = position_var;
        P_.get_ij(idx_pd_, idx_pd_) = position_var;
        P_.get_ij(idx_vn_, idx_vn_) = velocity_var;
        P_.get_ij(idx_ve_, idx_ve_) = velocity_var;
        P_.get_ij(idx_vd_, idx_vd_) = velocity_var;
        P_.get_ij(idx_a_tang_, idx_a_tang_) = acceleration_var;
        P_.get_ij(idx_omega_, idx_omega_) = acceleration_var;

        // Process noise: random walk on the tangential acceleration (driven
        // by jerk) and on the turn rate (driven by angular acceleration).
        // A single scalar drives both entries; the turn-rate units differ
        // (rad/s^2 vs ft/s^3) so this is a one-knob starting point to be
        // tuned, mirroring how the body-frame model lumps its three
        // acceleration channels under one process-noise std.
        const Real64 q = process_noise_std;
        const Real64 q2_dt = q * q * dt;

        Q_.zeros();
        Q_.get_ij(idx_a_tang_, idx_a_tang_) = q2_dt;
        Q_.get_ij(idx_omega_, idx_omega_) = q2_dt;
    }

    void UKF_ctra::predict()
    {
        if (generate_sigma_points_state())
        {
            // Propagate every sigma point through the nonlinear CTRA
            // kinematics over the full step.
            for (Uint32 i = 0; i < n_sigma_; ++i)
            {
                propagate_state(&sigma_pts_[i * state_dim_], dt_);
            }

            // Predicted state mean: x = sum(Wm_i * sigma_i).  Velocity is
            // stored in Cartesian (vn, ve), so no heading-angle unwrapping
            // is needed for the weighted mean.
            x_.zeros();
            for (Uint32 i = 0; i < n_sigma_; ++i)
            {
                for (Uint32 j = 0; j < state_dim_; ++j)
                {
                    x_[j] += wm_[i] * sigma_pts_[i * state_dim_ + j];
                }
            }

            // Predicted covariance: P = Q + sum(Wc_i * (sigma_i - x)(sigma_i - x)^T)
            P_.copy(Q_);
            for (Uint32 i = 0; i < n_sigma_; ++i)
            {
                Real64 dy[state_dim_];
                for (Uint32 j = 0; j < state_dim_; ++j)
                {
                    dy[j] = sigma_pts_[i * state_dim_ + j] - x_[j];
                }
                for (Uint32 r = 0; r < state_dim_; ++r)
                {
                    for (Uint32 c = 0; c < state_dim_; ++c)
                    {
                        P_.get_ij(r, c) += wc_[i] * dy[r] * dy[c];
                    }
                }
            }
        }
    }

    void UKF_ctra::propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const
    {
        if (pos_out != 0 && cov_out != 0)
        {
            // Local sigma points generated from the current state and
            // covariance (const: does not touch the member sigma buffer).
            // The unscented transform avoids the analytic Jacobian — and
            // hence the 1/vh heading derivative — entirely.
            Real64 local_sigmas[UKF_base::MAX_N_SIGMA * state_dim_];
            const bool ok = generate_sigma_points(x_.first(), P_, state_dim_,
                                                  local_sigmas, lambda_);
            if (ok)
            {
                for (Uint32 i = 0; i < n; ++i)
                {
                    if (i > 0)
                    {
                        // Advance every sigma point by one grid step.
                        for (Uint32 s = 0; s < n_sigma_; ++s)
                        {
                            propagate_state(&local_sigmas[s * state_dim_], dt);
                        }
                    }

                    // Weighted-mean position.
                    Real64 mean[3] = {0.0, 0.0, 0.0};
                    for (Uint32 s = 0; s < n_sigma_; ++s)
                    {
                        const Real64* sig = &local_sigmas[s * state_dim_];
                        mean[0] += wm_[s] * sig[idx_pn_];
                        mean[1] += wm_[s] * sig[idx_pe_];
                        mean[2] += wm_[s] * sig[idx_pd_];
                    }
                    pos_out[i * 3 + 0] = mean[0];
                    pos_out[i * 3 + 1] = mean[1];
                    pos_out[i * 3 + 2] = mean[2];

                    // Weighted position covariance: only the terms the
                    // cylinder test consumes (horizontal 2x2 + vertical
                    // variance), packed per State_estimator::Pos_cov_idx.
                    Real64 pnn = 0.0;
                    Real64 pne = 0.0;
                    Real64 pee = 0.0;
                    Real64 pdd = 0.0;
                    for (Uint32 s = 0; s < n_sigma_; ++s)
                    {
                        const Real64* sig = &local_sigmas[s * state_dim_];
                        const Real64 dn = sig[idx_pn_] - mean[0];
                        const Real64 de = sig[idx_pe_] - mean[1];
                        const Real64 dd = sig[idx_pd_] - mean[2];
                        pnn += wc_[s] * dn * dn;
                        pne += wc_[s] * dn * de;
                        pee += wc_[s] * de * de;
                        pdd += wc_[s] * dd * dd;
                    }
                    cov_out[i * COV_STRIDE + COV_PNN] = pnn;
                    cov_out[i * COV_STRIDE + COV_PNE] = pne;
                    cov_out[i * COV_STRIDE + COV_PEE] = pee;
                    cov_out[i * COV_STRIDE + COV_PDD] = pdd;
                }
            }
        }
    }

}  // namespace DAA
