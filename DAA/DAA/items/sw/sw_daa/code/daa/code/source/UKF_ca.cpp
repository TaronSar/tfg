// ---------------------------------------------------------------
// UKF_ca.cpp — UKF_ca non-inline method(s)
// ---------------------------------------------------------------
#include <UKF_ca.h>

namespace DAA
{

    UKF_ca::UKF_ca() :
            UKF_base(state_dim_, 3)
    {
    }

    void UKF_ca::initialize(const Real64* initial_pos,
                            Real64 dt,
                            Real64 process_noise_std,
                            Real64 position_var,
                            const Real64* initial_vel,
                            Real64 velocity_var,
                            Real64 acceleration_var)
    {
        dt_ = dt;

        // State: [n, e, d, vn, ve, vd, an, ae, ad]
        x_[idx_pn_] = initial_pos[0];
        x_[idx_pe_] = initial_pos[1];
        x_[idx_pd_] = initial_pos[2];
        x_[idx_vn_] = initial_vel[0];
        x_[idx_ve_] = initial_vel[1];
        x_[idx_vd_] = initial_vel[2];
        x_[idx_an_] = 0.0;
        x_[idx_ae_] = 0.0;
        x_[idx_ad_] = 0.0;

        // P = diag([position_var, velocity_var, acceleration_var])
        P_.zeros();
        P_.get_ij(idx_pn_, idx_pn_) = position_var;
        P_.get_ij(idx_pe_, idx_pe_) = position_var;
        P_.get_ij(idx_pd_, idx_pd_) = position_var;
        P_.get_ij(idx_vn_, idx_vn_) = velocity_var;
        P_.get_ij(idx_ve_, idx_ve_) = velocity_var;
        P_.get_ij(idx_vd_, idx_vd_) = velocity_var;
        P_.get_ij(idx_an_, idx_an_) = acceleration_var;
        P_.get_ij(idx_ae_, idx_ae_) = acceleration_var;
        P_.get_ij(idx_ad_, idx_ad_) = acceleration_var;

        // Process noise Q (jerk-driven CA model)
        const Real64 q = process_noise_std;
        const Real64 q2 = q * q;
        const Real64 dt2 = dt * dt;
        const Real64 dt3 = dt2 * dt;
        const Real64 dt4 = dt2 * dt2;
        const Real64 dt5 = dt4 * dt;

        Q_.zeros();
        // Per-axis 3x3 block over [pos, vel, acc] (vel offset = idx_vn_,
        // acc offset = idx_an_):
        //   [dt^5/20, dt^4/8, dt^3/6]
        //   [dt^4/8,  dt^3/3, dt^2/2]
        //   [dt^3/6,  dt^2/2, dt    ]
        for (Uint32 a = 0; a < 3; ++a)
        {
            const Uint32 p = a;            // pos index for this axis
            const Uint32 v = a + idx_vn_;  // vel index for this axis
            const Uint32 c = a + idx_an_;  // acc index for this axis

            Q_.get_ij(p, p) = q2 * dt5 / 20.0;  // pp
            Q_.get_ij(p, v) = q2 * dt4 / 8.0;   // pv
            Q_.get_ij(p, c) = q2 * dt3 / 6.0;   // pa
            Q_.get_ij(v, p) = q2 * dt4 / 8.0;   // vp
            Q_.get_ij(v, v) = q2 * dt3 / 3.0;   // vv
            Q_.get_ij(v, c) = q2 * dt2 / 2.0;   // va
            Q_.get_ij(c, p) = q2 * dt3 / 6.0;   // ap
            Q_.get_ij(c, v) = q2 * dt2 / 2.0;   // av
            Q_.get_ij(c, c) = q2 * dt;          // aa
        }
    }

    void UKF_ca::predict()
    {
        // Generate sigma points from current state
        if (generate_sigma_points_state())
        {
            const Real64 half_dt2 = 0.5 * dt_ * dt_;

            // Propagate each sigma point through CA model:
            //   p_{k+1} = p_k + v_k*dt + 0.5*a_k*dt^2
            //   v_{k+1} = v_k + a_k*dt
            //   a_{k+1} = a_k
            for (Uint32 i = 0; i < n_sigma_; ++i)
            {
                Real64* sp = &sigma_pts_[i * state_dim_];
                sp[idx_pn_] += sp[idx_vn_] * dt_ + sp[idx_an_] * half_dt2;  // north
                sp[idx_pe_] += sp[idx_ve_] * dt_ + sp[idx_ae_] * half_dt2;  // east
                sp[idx_pd_] += sp[idx_vd_] * dt_ + sp[idx_ad_] * half_dt2;  // down
                sp[idx_vn_] += sp[idx_an_] * dt_;                           // vn
                sp[idx_ve_] += sp[idx_ae_] * dt_;                           // ve
                sp[idx_vd_] += sp[idx_ad_] * dt_;                           // vd
                // acceleration unchanged
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

    void UKF_ca::propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const
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
            const Real64 an = x_[idx_an_];
            const Real64 ae = x_[idx_ae_];
            const Real64 ad = x_[idx_ad_];

            // (r,c) of the position-covariance terms emitted per sample,
            // packed per State_estimator::Pos_cov_idx.
            static const Uint32 rc[4][2] = { {0, 0}, {0, 1}, {1, 1}, {2, 2} };

            for (Uint32 i = 0; i < n; ++i)
            {
                const Real64 t = static_cast<Real64>(i) * dt;
                const Real64 t2 = t * t;
                const Real64 ht2 = 0.5 * t2;

                pos_out[i * 3 + 0] = n0 + vn * t + an * ht2;
                pos_out[i * 3 + 1] = e0 + ve * t + ae * ht2;
                pos_out[i * 3 + 2] = d0 + vd * t + ad * ht2;

                // Only the covariance terms consumed by the cylinder test
                // are emitted (horizontal 2x2 + vertical variance), packed
                // per State_estimator::Pos_cov_idx.
                // P_pos(t)[r,c] = P_pp
                //          + t   * (P_pv + P_vp)
                //          + ht2 * (P_pa + P_ap)
                //          + t2  *  P_vv
                //          + t*ht2 * (P_va + P_av)
                //          + ht2*ht2 * P_aa
                for (Uint32 k = 0; k < 4; ++k)
                {
                    const Uint32 r = rc[k][0];
                    const Uint32 c = rc[k][1];

                    const Real64 Ppp = P_.get_ij(r, c);
                    const Real64 Ppv = P_.get_ij(r, c + idx_vn_);
                    const Real64 Pvp = P_.get_ij(r + idx_vn_, c);
                    const Real64 Ppa = P_.get_ij(r, c + idx_an_);
                    const Real64 Pap = P_.get_ij(r + idx_an_, c);
                    const Real64 Pvv = P_.get_ij(r + idx_vn_, c + idx_vn_);
                    const Real64 Pva = P_.get_ij(r + idx_vn_, c + idx_an_);
                    const Real64 Pav = P_.get_ij(r + idx_an_, c + idx_vn_);
                    const Real64 Paa = P_.get_ij(r + idx_an_, c + idx_an_);

                    cov_out[i * COV_STRIDE + k] = Ppp + t * (Ppv + Pvp) + ht2 * (Ppa + Pap) + t2 * Pvv +
                                                  t * ht2 * (Pva + Pav) + ht2 * ht2 * Paa;
                }
            }
        }
    }

}  // namespace DAA
