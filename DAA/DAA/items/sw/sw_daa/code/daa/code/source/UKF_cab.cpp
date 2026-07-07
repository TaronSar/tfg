// ---------------------------------------------------------------
// UKF_cab.cpp — UKF_cab non-inline method(s)
// ---------------------------------------------------------------
#include <Rmath.h>
#include <UKF_cab.h>

namespace DAA
{

    UKF_cab::UKF_cab() :
            UKF_base(state_dim_, 3)
    {
    }

    void UKF_cab::body_to_ned_accel(const Real64* vel, const Real64* a_body, Real64* a_ned)
    {
        // Horizontal-speed regularization.  The body->NED rotation heading
        // cp = vn/vh, sp = ve/vh is undefined as the horizontal speed
        // vh -> 0: a vanishing velocity yields an arbitrary heading, so the
        // same body-frame (tangential / normal) acceleration maps to wildly
        // different NED directions.  In the UKF predict step this lets
        // sigma points whose velocity straddles zero rotate the same
        // acceleration into opposing directions, inflating the velocity
        // covariance and the position/velocity cross-covariance until the
        // measurement update applies a huge spurious correction (the
        // velocity "spike" seen at low estimated speed).  Flooring the
        // speed used in the rotation, vh_eff = max(vh, VH_MIN), keeps the
        // heading well-conditioned and smoothly attenuates the horizontal
        // acceleration contribution below VH_MIN (cp, sp -> 0 as vh -> 0),
        // so a low-speed estimate can no longer be whipped around or
        // decelerated past zero.  The vertical channel is unaffected.
        // VH_MIN is set to the minimum plausible horizontal airspeed of a
        // tracked aircraft (a real intruder does not loiter below this),
        // matching the VH_THRESHOLD used by the covariance Jacobian in
        // integrate_segment().
        const Real64 VH_MIN = 15.24;  // m/s
        const Real64 vh = Rmath::sqrtr(vel[0] * vel[0] + vel[1] * vel[1]);
        const Real64 vh_eff = (vh > VH_MIN) ? vh : VH_MIN;
        const Real64 cp = vel[0] / vh_eff;
        const Real64 sp = vel[1] / vh_eff;
        a_ned[0] = a_body[0] * cp - a_body[1] * sp;
        a_ned[1] = a_body[0] * sp + a_body[1] * cp;
        a_ned[2] = a_body[2];
    }

    void UKF_cab::initialize(const Real64* initial_pos,
                             Real64 dt,
                             Real64 process_noise_std,
                             Real64 position_var,
                             const Real64* initial_vel,
                             Real64 velocity_var,
                             Real64 acceleration_var)
    {
        dt_ = dt;

        // State: [n, e, d, vn, ve, vd, a_tang, a_norm, a_vert]
        x_[idx_pn_] = initial_pos[0];
        x_[idx_pe_] = initial_pos[1];
        x_[idx_pd_] = initial_pos[2];
        x_[idx_vn_] = initial_vel[0];
        x_[idx_ve_] = initial_vel[1];
        x_[idx_vd_] = initial_vel[2];
        x_[idx_a_tang_] = 0.0;
        x_[idx_a_norm_] = 0.0;
        x_[idx_a_vert_] = 0.0;

        // P = diag([position_var, velocity_var, acceleration_var])
        P_.zeros();
        P_.get_ij(idx_pn_, idx_pn_) = position_var;
        P_.get_ij(idx_pe_, idx_pe_) = position_var;
        P_.get_ij(idx_pd_, idx_pd_) = position_var;
        P_.get_ij(idx_vn_, idx_vn_) = velocity_var;
        P_.get_ij(idx_ve_, idx_ve_) = velocity_var;
        P_.get_ij(idx_vd_, idx_vd_) = velocity_var;
        P_.get_ij(idx_a_tang_, idx_a_tang_) = acceleration_var;
        P_.get_ij(idx_a_norm_, idx_a_norm_) = acceleration_var;
        P_.get_ij(idx_a_vert_, idx_a_vert_) = acceleration_var;

        // Process noise: random walk on body-frame acceleration (driven by jerk)
        const Real64 q = process_noise_std;
        const Real64 q2_dt = q * q * dt;

        Q_.zeros();
        Q_.get_ij(idx_a_tang_, idx_a_tang_) = q2_dt;
        Q_.get_ij(idx_a_norm_, idx_a_norm_) = q2_dt;
        Q_.get_ij(idx_a_vert_, idx_a_vert_) = q2_dt;
    }

    void UKF_cab::predict()
    {
        // Generate sigma points from current state
        if (generate_sigma_points_state())
        {
            // Sub-step the propagation so the heading-dependent NED
            // acceleration is re-evaluated during turns.
            Uint32 n_sub = static_cast<Uint32>(dt_ * 10.0);
            if (n_sub < 1)
            {
                n_sub = 1;
            }
            const Real64 h = dt_ / static_cast<Real64>(n_sub);

            // Propagate each sigma point through the CAB model using Heun
            // (velocity-midpoint) integration.  Body-frame acceleration is
            // held constant; NED acceleration is recomputed each sub-step.
            for (Uint32 i = 0; i < n_sigma_; ++i)
            {
                Real64* sp = &sigma_pts_[i * state_dim_];
                for (Uint32 s = 0; s < n_sub; ++s)
                {
                    Real64 a1[3];
                    body_to_ned_accel(&sp[idx_vn_], &sp[idx_a_tang_], a1);

                    Real64 v_pred[3];
                    v_pred[0] = sp[idx_vn_] + a1[0] * h;
                    v_pred[1] = sp[idx_ve_] + a1[1] * h;
                    v_pred[2] = sp[idx_vd_] + a1[2] * h;

                    Real64 a2[3];
                    body_to_ned_accel(v_pred, &sp[idx_a_tang_], a2);

                    const Real64 a_avg0 = 0.5 * (a1[0] + a2[0]);
                    const Real64 a_avg1 = 0.5 * (a1[1] + a2[1]);
                    const Real64 a_avg2 = 0.5 * (a1[2] + a2[2]);

                    sp[idx_pn_] += sp[idx_vn_] * h + 0.5 * a_avg0 * h * h;
                    sp[idx_pe_] += sp[idx_ve_] * h + 0.5 * a_avg1 * h * h;
                    sp[idx_pd_] += sp[idx_vd_] * h + 0.5 * a_avg2 * h * h;
                    sp[idx_vn_] += a_avg0 * h;
                    sp[idx_ve_] += a_avg1 * h;
                    sp[idx_vd_] += a_avg2 * h;
                    // body-frame acceleration unchanged
                }
            }

            // Predicted state mean: x = sum(Wm_i * sigma_i)
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

    void UKF_cab::integrate_segment(Real64 tau, Real64* p, Real64* v, const Real64* a_body, Real64* cov9)
    {
        // Heading-freeze thresholds: see the Python reference.  Below
        // VH_BLEND the Jacobian heading is fully frozen; above VH_THRESHOLD
        // it is fully live; in between it is blended linearly.
        const Real64 VH_THRESHOLD = 15.24;  // m/s
        const Real64 VH_BLEND = 6.096;      // m/s

        Uint32 n_steps = static_cast<Uint32>(Rmath::fabsr(tau) * 10.0);
        if (n_steps < 1)
        {
            n_steps = 1;
        }
        const Real64 h = tau / static_cast<Real64>(n_steps);

        // Frozen-heading seed from the input velocity.
        Real64 cp_jac = 1.0;
        Real64 sp_jac = 0.0;
        const Real64 vh0 = Rmath::sqrtr(v[0] * v[0] + v[1] * v[1]);
        if (vh0 > VH_BLEND)
        {
            cp_jac = v[0] / vh0;
            sp_jac = v[1] / vh0;
        }

        for (Uint32 step = 0; step < n_steps; ++step)
        {
            const Real64 vh2 = v[0] * v[0] + v[1] * v[1];
            const Real64 vh = Rmath::sqrtr(vh2);

            Real64 cp = 1.0;
            Real64 sp = 0.0;
            if (vh > 1e-6)
            {
                cp = v[0] / vh;
                sp = v[1] / vh;
            }

            // Heun (velocity-midpoint) integration
            Real64 a1[3];
            a1[0] = a_body[0] * cp - a_body[1] * sp;
            a1[1] = a_body[0] * sp + a_body[1] * cp;
            a1[2] = a_body[2];

            Real64 v_pred[3];
            v_pred[0] = v[0] + a1[0] * h;
            v_pred[1] = v[1] + a1[1] * h;
            v_pred[2] = v[2] + a1[2] * h;

            const Real64 vh_p = Rmath::sqrtr(v_pred[0] * v_pred[0] + v_pred[1] * v_pred[1]);
            Real64 cp2 = cp;
            Real64 sp2 = sp;
            if (vh_p > 1e-6)
            {
                cp2 = v_pred[0] / vh_p;
                sp2 = v_pred[1] / vh_p;
            }

            Real64 a2[3];
            a2[0] = a_body[0] * cp2 - a_body[1] * sp2;
            a2[1] = a_body[0] * sp2 + a_body[1] * cp2;
            a2[2] = a_body[2];

            const Real64 a_avg0 = 0.5 * (a1[0] + a2[0]);
            const Real64 a_avg1 = 0.5 * (a1[1] + a2[1]);
            const Real64 a_avg2 = 0.5 * (a1[2] + a2[2]);

            p[0] += v[0] * h + 0.5 * a_avg0 * h * h;
            p[1] += v[1] * h + 0.5 * a_avg1 * h * h;
            p[2] += v[2] * h + 0.5 * a_avg2 * h * h;
            v[0] += a_avg0 * h;
            v[1] += a_avg1 * h;
            v[2] += a_avg2 * h;

            if (cov9 != 0)
            {
                // Update frozen heading while speed is meaningful.
                if (vh > VH_BLEND)
                {
                    cp_jac = cp;
                    sp_jac = sp;
                }

                // Blend factor: 1 = use live heading, 0 = use frozen heading.
                Real64 alpha_blend = 0.0;
                if (vh >= VH_THRESHOLD)
                {
                    alpha_blend = 1.0;
                }
                else if (vh > VH_BLEND)
                {
                    alpha_blend = (vh - VH_BLEND) / (VH_THRESHOLD - VH_BLEND);
                }

                const Real64 cp_eff = alpha_blend * cp + (1.0 - alpha_blend) * cp_jac;
                const Real64 sp_eff = alpha_blend * sp + (1.0 - alpha_blend) * sp_jac;

                const Real64 a_N_eff = a_body[0] * cp_eff - a_body[1] * sp_eff;
                const Real64 a_E_eff = a_body[0] * sp_eff + a_body[1] * cp_eff;

                // d(a_NED)/dv (3x3); ramps to zero as vh enters the blend zone.
                Real64 da_dv[9] = {0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0};
                if (vh > VH_BLEND)
                {
                    da_dv[0] = alpha_blend * (a_E_eff * v[1] / vh2);
                    da_dv[1] = alpha_blend * (-a_E_eff * v[0] / vh2);
                    da_dv[3] = alpha_blend * (-a_N_eff * v[1] / vh2);
                    da_dv[4] = alpha_blend * (a_N_eff * v[0] / vh2);
                }

                // R(psi): rotation from body to NED (blended heading).
                Real64 R_psi[9] = {cp_eff, -sp_eff, 0.0, sp_eff, cp_eff, 0.0, 0.0, 0.0, 1.0};

                // 9x9 step Jacobian F (row-major), built as identity then
                // populated with the position/velocity coupling blocks.
                Real64 F[81];
                for (Uint32 r = 0; r < 9; ++r)
                {
                    for (Uint32 c = 0; c < 9; ++c)
                    {
                        F[r * 9 + c] = (r == c) ? 1.0 : 0.0;
                    }
                }

                const Real64 half_h2 = 0.5 * h * h;
                for (Uint32 r = 0; r < 3; ++r)
                {
                    for (Uint32 c = 0; c < 3; ++c)
                    {
                        const Real64 ident = (r == c) ? 1.0 : 0.0;
                        // F[0:3, 3:6] = I*h + 0.5*h^2 * da_dv
                        F[r * 9 + (3 + c)] = ident * h + half_h2 * da_dv[r * 3 + c];
                        // F[0:3, 6:9] = 0.5*h^2 * R_psi
                        F[r * 9 + (6 + c)] = half_h2 * R_psi[r * 3 + c];
                        // F[3:6, 3:6] = I + h * da_dv
                        F[(3 + r) * 9 + (3 + c)] = ident + h * da_dv[r * 3 + c];
                        // F[3:6, 6:9] = h * R_psi
                        F[(3 + r) * 9 + (6 + c)] = h * R_psi[r * 3 + c];
                    }
                }

                // P = F * P * F^T  (via tmp = F * P, then P = tmp * F^T)
                Real64 tmp[81];
                for (Uint32 r = 0; r < 9; ++r)
                {
                    for (Uint32 c = 0; c < 9; ++c)
                    {
                        Real64 acc = 0.0;
                        for (Uint32 k = 0; k < 9; ++k)
                        {
                            acc += F[r * 9 + k] * cov9[k * 9 + c];
                        }
                        tmp[r * 9 + c] = acc;
                    }
                }
                for (Uint32 r = 0; r < 9; ++r)
                {
                    for (Uint32 c = 0; c < 9; ++c)
                    {
                        Real64 acc = 0.0;
                        for (Uint32 k = 0; k < 9; ++k)
                        {
                            acc += tmp[r * 9 + k] * F[c * 9 + k];
                        }
                        cov9[r * 9 + c] = acc;
                    }
                }
            }
        }
    }

    void UKF_cab::propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const
    {
        if (pos_out != 0 && cov_out != 0)
        {
            Real64 p[3];
            Real64 v[3];
            Real64 a_body[3];
            p[0] = x_[idx_pn_];
            p[1] = x_[idx_pe_];
            p[2] = x_[idx_pd_];
            v[0] = x_[idx_vn_];
            v[1] = x_[idx_ve_];
            v[2] = x_[idx_vd_];
            a_body[0] = x_[idx_a_tang_];
            a_body[1] = x_[idx_a_norm_];
            a_body[2] = x_[idx_a_vert_];

            // Running full 9x9 covariance (row-major), seeded from P_.
            Real64 cov9[81];
            for (Uint32 r = 0; r < state_dim_; ++r)
            {
                for (Uint32 c = 0; c < state_dim_; ++c)
                {
                    cov9[r * 9 + c] = P_.get_ij(r, c);
                }
            }

            // (r,c) of the position-covariance terms emitted per sample,
            // packed per State_estimator::Pos_cov_idx.
            static const Uint32 rc[4][2] = { {0, 0}, {0, 1}, {1, 1}, {2, 2} };

            for (Uint32 i = 0; i < n; ++i)
            {
                if (i > 0)
                {
                    // Position and covariance advance together by one grid
                    // step using the local Jacobian at each sub-step.
                    integrate_segment(dt, p, v, a_body, cov9);
                }

                pos_out[i * 3 + 0] = p[0];
                pos_out[i * 3 + 1] = p[1];
                pos_out[i * 3 + 2] = p[2];

                // Emit only the position-covariance terms consumed by the
                // cylinder test (horizontal 2x2 + vertical variance) from
                // the running 9x9, packed per State_estimator::Pos_cov_idx.
                for (Uint32 k = 0; k < 4; ++k)
                {
                    cov_out[i * COV_STRIDE + k] = cov9[rc[k][0] * 9 + rc[k][1]];
                }
            }
        }
    }

}  // namespace DAA
