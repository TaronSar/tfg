// ---------------------------------------------------------------
// State_estimator.cpp — State_estimator non-inline method(s)
// ---------------------------------------------------------------
#include <Rfun.h>
#include <State_estimator.h>

namespace DAA
{

    State_estimator::State_estimator(Uint32 dim_x, Uint32 dim_z) :
            dim_x_(dim_x),
            dim_z_(dim_z),
            dt_(0.0)
    {
        x_.resize(dim_x_);
        x_.zeros();
        P_.resize_mat(dim_x_, dim_x_);
        P_.eye();
        Q_.resize_mat(dim_x_, dim_x_);
        Q_.zeros();
    }

    void State_estimator::set_process_noise_diag(const Real64* q_var_diag)
    {
        if (q_var_diag != 0)
        {
            Q_.zeros();
            for (Uint32 i = 0; i < dim_x_; ++i)
            {
                Q_.get_ij(i, i) = q_var_diag[i];
            }
        }
    }

    Real64 State_estimator::min_1sigma_cylinder_distance(const Real64* own_traj,
                                                         const Real64* int_pos,
                                                         const Real64* int_cov,
                                                         Uint32 N,
                                                         Real64 cyl_h,
                                                         Real64 cyl_d,
                                                         int* idx_cpa_out) const
    {
        /// \wi{0}
        const Real64 half_h = cyl_h * 0.5;
        const Real64 radius = cyl_d * 0.5;

        if (N == 0)
        {
            if (idx_cpa_out != 0)
            {
                *idx_cpa_out = -1;
            }
            return 1.0e30;
        }

        Real64 min_dist = 1.0e30;
        Uint32 i_cpa = 0;

        for (Uint32 i = 0; (i < N) && (min_dist >= 1.0); ++i)
        {
            // Ownship future position supplied by caller.
            const Real64 own_n = own_traj[i * 3 + 0];
            const Real64 own_e = own_traj[i * 3 + 1];
            const Real64 own_d = own_traj[i * 3 + 2];

            // Relative position (intruder - ownship)
            const Real64 rel_n = int_pos[i * 3 + 0] - own_n;
            const Real64 rel_e = int_pos[i * 3 + 1] - own_e;
            const Real64 rel_d = int_pos[i * 3 + 2] - own_d;

            const Real64 horiz = Rmath::sqrtr(rel_n * rel_n + rel_e * rel_e);

            // Unit vector in horizontal plane (towards intruder)
            Real64 u0;
            Real64 u1;
            if (horiz > 1.0e-6)
            {
                u0 = rel_n / horiz;
                u1 = rel_e / horiz;
            }
            else
            {
                u0 = 1.0;
                u1 = 0.0;
            }

            // 1-sigma radial std = sqrt(u^T P_pos_2x2 u)
            const Real64* Pp = &int_cov[i * COV_STRIDE];
            const Real64 quad = u0 * (u0 * Pp[COV_PNN] + u1 * Pp[COV_PNE]) +
                                u1 * (u0 * Pp[COV_PNE] + u1 * Pp[COV_PEE]);
            const Real64 rad_std = Rfun::safe_sqrt(quad);

            // 1-sigma vertical std
            const Real64 down_var = Pp[COV_PDD];
            const Real64 down_std = Rfun::safe_sqrt(down_var);

            // Cylinder distance components
            const Real64 d_xy = horiz / (radius + rad_std);
            const Real64 abs_rel_d = Rmath::fabsr(rel_d);
            const Real64 d_z = abs_rel_d / (half_h + down_std);

            const Real64 d = d_xy > d_z ? d_xy : d_z;
            if (d < min_dist)
            {
                min_dist = d;
                i_cpa = i;
            }
        }

        if (idx_cpa_out != 0)
        {
            *idx_cpa_out = static_cast<int>(i_cpa);
        }
        return min_dist;
    }

}  // namespace DAA
