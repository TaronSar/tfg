// ---------------------------------------------------------------
// UKF_cv.cpp — UKF_cv non-inline method(s)
// ---------------------------------------------------------------
#include <UKF_cv.h>

namespace DAA
{

    UKF_cv::UKF_cv() :
            UKF_base(state_dim_, 3)
    {
    }

    void UKF_cv::initialize(const Real64* initial_pos,
                            Real64 dt,
                            Real64 process_noise_std,
                            Real64 position_var,
                            const Real64* initial_vel,
                            Real64 velocity_var,
                            Real64)
    {
        // acceleration_var is intentionally unused: the CV model has no
        // acceleration state.  It exists so the signature matches the
        // unified UKF_base::initialize interface.
        dt_ = dt;

        // State: [n, e, d, vn, ve, vd]
        x_[idx_pn_] = initial_pos[0];
        x_[idx_pe_] = initial_pos[1];
        x_[idx_pd_] = initial_pos[2];
        x_[idx_vn_] = initial_vel[0];
        x_[idx_ve_] = initial_vel[1];
        x_[idx_vd_] = initial_vel[2];

        // P = diag([position_var, velocity_var])
        P_.zeros();
        P_.get_ij(idx_pn_, idx_pn_) = position_var;
        P_.get_ij(idx_pe_, idx_pe_) = position_var;
        P_.get_ij(idx_pd_, idx_pd_) = position_var;
        P_.get_ij(idx_vn_, idx_vn_) = velocity_var;
        P_.get_ij(idx_ve_, idx_ve_) = velocity_var;
        P_.get_ij(idx_vd_, idx_vd_) = velocity_var;

        // Process noise Q (jerk-driven CV model)
        const Real64 q = process_noise_std;
        const Real64 q2 = q * q;
        const Real64 dt2 = dt * dt;
        const Real64 dt3 = dt2 * dt;
        const Real64 dt4 = dt2 * dt2;

        Q_.zeros();
        // Diagonal blocks per axis (vel offset = idx_vn_):
        //   [dt^4/4,  dt^3/2]
        //   [dt^3/2,  dt^2  ]
        for (Uint32 a = 0; a < 3; ++a)
        {
            const Uint32 v = a + idx_vn_;
            Q_.get_ij(a, a) = q2 * dt4 / 4.0;      // pp
            Q_.get_ij(a, v) = q2 * dt3 / 2.0;      // pv
            Q_.get_ij(v, a) = q2 * dt3 / 2.0;      // vp
            Q_.get_ij(v, v) = q2 * dt2;            // vv
        }
    }

    void UKF_cv::predict()
    {
        // Generate sigma points from current state
        if (generate_sigma_points_state())
        {
            // Propagate each sigma point through CV model
            for (Uint32 i = 0; i < n_sigma_; ++i)
            {
                Real64* sp = &sigma_pts_[i * state_dim_];
                sp[idx_pn_] += sp[idx_vn_] * dt_;  // north += vn * dt
                sp[idx_pe_] += sp[idx_ve_] * dt_;  // east  += ve * dt
                sp[idx_pd_] += sp[idx_vd_] * dt_;  // down  += vd * dt
                // velocity unchanged
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

    void UKF_cv::propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const
    {
        if (pos_out != 0 && cov_out != 0)
        {
            // Stack copy for speed
            const Real64 n0 = x_[idx_pn_];
            const Real64 e0 = x_[idx_pe_];
            const Real64 d0 = x_[idx_pd_];
            const Real64 vn = x_[idx_vn_];
            const Real64 ve = x_[idx_ve_];
            const Real64 vd = x_[idx_vd_];

            // (r,c) of the position-covariance terms emitted per sample,
            // packed per State_estimator::Pos_cov_idx.
            static const Uint32 rc[4][2] = { {0, 0}, {0, 1}, {1, 1}, {2, 2} };

            for (Uint32 i = 0; i < n; ++i)
            {
                const Real64 t = static_cast<Real64>(i) * dt;
                const Real64 t2 = t * t;

                pos_out[i * 3 + 0] = n0 + vn * t;
                pos_out[i * 3 + 1] = e0 + ve * t;
                pos_out[i * 3 + 2] = d0 + vd * t;

                // Only the covariance terms consumed by the cylinder test
                // are emitted (horizontal 2x2 + vertical variance), packed
                // per State_estimator::Pos_cov_idx.
                // P_pos(t)[r,c] = P_pp + t*(P_pv + P_vp) + t^2 * P_vv
                for (Uint32 k = 0; k < 4; ++k)
                {
                    const Uint32 r = rc[k][0];
                    const Uint32 c = rc[k][1];

                    const Real64 Ppp = P_.get_ij(r, c);
                    const Real64 Ppv = P_.get_ij(r, c + idx_vn_);
                    const Real64 Pvp = P_.get_ij(r + idx_vn_, c);
                    const Real64 Pvv = P_.get_ij(r + idx_vn_, c + idx_vn_);

                    cov_out[i * COV_STRIDE + k] = Ppp + t * (Ppv + Pvp) + t2 * Pvv;
                }
            }
        }
    }

}  // namespace DAA
