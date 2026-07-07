// ---------------------------------------------------------------
// UKF_base.cpp — UKF_base non-inline method(s)
// ---------------------------------------------------------------
#include <UKF_base.h>

#include <cmath>
#include <cstring>

namespace DAA
{

    UKF_base::UKF_base(Uint32 dim_x, Uint32 dim_z) :
            State_estimator(dim_x, dim_z),
            n_sigma_(2 * dim_x + 1),
            alpha_(1e-3),
            beta_(2.0),
            kappa_(3.0 - static_cast<Real64>(dim_x)),
            lambda_(0.0)
    {
        compute_weights();
        memset(sigma_pts_, 0, static_cast<size_t>(n_sigma_ * dim_x_) * sizeof(Real64));
        memset(sigma_z_, 0, static_cast<size_t>(n_sigma_ * dim_z_) * sizeof(Real64));
    }

    bool UKF_base::generate_sigma_points(const Real64* x,
                                         const Maverick::R64matrix& P,
                                         Uint32 dim,
                                         Real64* out,
                                         Real64 lambda_val) const
    {
        // sigma[0] = x
        memcpy(out, x, static_cast<size_t>(dim) * sizeof(Real64));

        // Compute L such that L*L^T = (dim + lambda) * P via Cholesky.
        // Scale P into L, then decompose in-place.
        Maverick::R64matrixn<MAX_DIM_X> L;
        L.resize_mat(static_cast<Uint16>(dim), static_cast<Uint16>(dim));
        const Real64 scale = static_cast<Real64>(dim) + lambda_val;
        for (Uint32 c = 0; c < dim; ++c)
        {
            for (Uint32 r = 0; r < dim; ++r)
            {
                L.get_ij(r, c) = P.get_ij(r, c) * scale;
            }
        }

        if (!L.cholesky_decomp())
        {
            return false;
        }

        // L is now lower-triangular (column-major).
        // Column i of L = row i of L^T.
        // sigma[i+1]     = x + column_i(L)
        // sigma[i+1+dim] = x - column_i(L)
        for (Uint32 i = 0; i < dim; ++i)
        {
            for (Uint32 j = 0; j < dim; ++j)
            {
                Real64 lji = L.get_ij(j, i);
                out[(i + 1) * dim + j] = x[j] + lji;
                out[(i + 1 + dim) * dim + j] = x[j] - lji;
            }
        }
        return true;
    }

    // ---- Measurement-driven bootstrap (first-sighting initialise) ----
    void UKF_base::initialize_from_measurement(const Real64* z,
                                               const Real64* ownship_pos,
                                               const Real64* ownship_att,
                                               const Real64* ownship_cov,
                                               Real64 dt,
                                               Real64 process_noise_std,
                                               const Real64* meas_noise_std,
                                               Real64 velocity_var,
                                               Real64 acceleration_var,
                                               Real64 velocity_var_vertical,
                                               Real64 acceleration_var_vertical,
                                               const Real64* q_var_diag,
                                               Uint32 q_n)
    {
        const Real64 az = z[0];
        const Real64 el = z[1];
        const Real64 rng = z[2];

        const Real64 ca = cos(az);
        const Real64 sa = sin(az);
        const Real64 ce = cos(el);
        const Real64 se = sin(el);

        // Body-frame line-of-sight vector b and its partial derivatives
        // with respect to (azimuth, elevation, range).
        Real64 b[3];
        b[0] = rng * ce * ca;
        b[1] = rng * ce * sa;
        b[2] = -rng * se;

        Real64 db_az[3];
        db_az[0] = -rng * ce * sa;
        db_az[1] = rng * ce * ca;
        db_az[2] = 0.0;

        Real64 db_el[3];
        db_el[0] = -rng * se * ca;
        db_el[1] = -rng * se * sa;
        db_el[2] = -rng * ce;

        Real64 db_rng[3];
        db_rng[0] = ce * ca;
        db_rng[1] = ce * sa;
        db_rng[2] = -se;

        // Body -> NED rotation M (3-2-1 Euler), the inverse of the
        // body-frame rotation used by measurement_function().
        const Real64 cy = cos(ownship_att[2]);
        const Real64 sy = sin(ownship_att[2]);
        const Real64 cp = cos(ownship_att[1]);
        const Real64 spch = sin(ownship_att[1]);
        const Real64 cr = cos(ownship_att[0]);
        const Real64 sr = sin(ownship_att[0]);

        Real64 m[3][3];
        m[0][0] = cp * cy;
        m[0][1] = sr * spch * cy - cr * sy;
        m[0][2] = cr * spch * cy + sr * sy;
        m[1][0] = cp * sy;
        m[1][1] = sr * spch * sy + cr * cy;
        m[1][2] = cr * spch * sy - sr * cy;
        m[2][0] = -spch;
        m[2][1] = sr * cp;
        m[2][2] = cr * cp;

        // Back-projected NED position: p = ownship_pos + M * b.
        Real64 pos[3];
        for (Uint32 r = 0; r < 3; ++r)
        {
            pos[r] = ownship_pos[r]
                   + m[r][0] * b[0] + m[r][1] * b[1] + m[r][2] * b[2];
        }

        // Measurement-space Jacobian rotated to NED: columns are the
        // NED sensitivities to (azimuth, elevation, range).
        Real64 j_az[3];
        Real64 j_el[3];
        Real64 j_rng[3];
        for (Uint32 r = 0; r < 3; ++r)
        {
            j_az[r] = m[r][0] * db_az[0] + m[r][1] * db_az[1] + m[r][2] * db_az[2];
            j_el[r] = m[r][0] * db_el[0] + m[r][1] * db_el[1] + m[r][2] * db_el[2];
            j_rng[r] = m[r][0] * db_rng[0] + m[r][1] * db_rng[1] + m[r][2] * db_rng[2];
        }

        // Anisotropic position covariance P_pos = J * R * J^T plus the
        // ownship position covariance (top-left 3x3 block of the 6x6).
        const Real64 var_az = meas_noise_std[0] * meas_noise_std[0];
        const Real64 var_el = meas_noise_std[1] * meas_noise_std[1];
        const Real64 var_rng = meas_noise_std[2] * meas_noise_std[2];

        Real64 p_pos[3][3];
        for (Uint32 r = 0; r < 3; ++r)
        {
            for (Uint32 c = 0; c < 3; ++c)
            {
                p_pos[r][c] = var_az * j_az[r] * j_az[c]
                            + var_el * j_el[r] * j_el[c]
                            + var_rng * j_rng[r] * j_rng[c]
                            + ownship_cov[(r * 6) + c];
            }
        }

        // Seed the model layout (state, Q, R, velocity / acceleration
        // covariance) through the per-model initialise with zero
        // velocity.  The isotropic position_var passed here is a sane
        // fallback; the anisotropic block below overwrites it.
        Real64 zero_vel[3] = {0.0, 0.0, 0.0};
        const Real64 pos_var_repr = (p_pos[0][0] + p_pos[1][1] + p_pos[2][2]) / 3.0;
        initialize(pos, dt, process_noise_std,
                   pos_var_repr, zero_vel, velocity_var, acceleration_var);

        // Overwrite the position covariance block with the anisotropic
        // one (state index 0..2 = n, e, d for every motion model).
        for (Uint32 r = 0; r < 3; ++r)
        {
            for (Uint32 c = 0; c < 3; ++c)
            {
                P_.get_ij(r, c) = p_pos[r][c];
            }
        }

        // Aircraft trajectories are largely level, so the vertical rate
        // is far more tightly bounded than the horizontal speed.  The
        // per-model initialise above seeded all three velocity axes with
        // the (horizontal) velocity_var; overwrite the down-velocity
        // entry (state index 5 for every motion model) with the tighter
        // vertical variance so the predicted altitude envelope does not
        // fan out over the lookahead horizon.  Likewise overwrite the
        // vertical acceleration entry (state index 8) for the CA / CAB
        // models that carry an acceleration state (dim_x_ >= 9); the CV
        // model (dim_x_ == 6) has no acceleration state to seed.
        P_.get_ij(5, 5) = velocity_var_vertical;
        if (dim_x_ >= 9)
        {
            P_.get_ij(8, 8) = acceleration_var_vertical;
        }
        else if (dim_x_ == 8)
        {
            // CTRA (8-state) carries the horizontal turn rate as its 8th
            // state (index 7) in place of the body-frame model's vertical
            // acceleration (index 8).  Seed it from the vertical-
            // acceleration variance slot, which the caller repurposes as
            // the initial turn-rate variance for this model.
            P_.get_ij(7, 7) = acceleration_var_vertical;
        }

        // Optional per-channel process-noise override.  The per-model
        // initialise above built Q from the lumped scalar; when the
        // caller supplies a full diagonal (length == state dimension)
        // replace Q's diagonal so each channel can be tuned
        // independently (the CTRA model needs this — its tangential-
        // acceleration and turn-rate channels carry different physical
        // quantities and need very different magnitudes).
        if ((q_var_diag != 0) && (q_n == dim_x_))
        {
            set_process_noise_diag(q_var_diag);
        }
    }

    // ---- Measurement function: NED state -> [az, el, range] in body frame ----
    void UKF_base::measurement_function(const Real64* state,
                                        const Real64* ownship_pos,
                                        const Real64* ownship_att,
                                        Real64* z_out)
    {
        // Relative NED
        Real64 rel_n = state[0] - ownship_pos[0];
        Real64 rel_e = state[1] - ownship_pos[1];
        Real64 rel_d = state[2] - ownship_pos[2];

        Real64 roll = ownship_att[0];
        Real64 pitch = ownship_att[1];
        Real64 yaw = ownship_att[2];

        Real64 cr = cos(roll), sr = sin(roll);
        Real64 cp = cos(pitch), sp = sin(pitch);
        Real64 cy = cos(yaw), sy = sin(yaw);

        // R_body_ned = R_roll * R_pitch * R_yaw  (3-2-1 rotation)
        // body = R_roll * R_pitch * R_yaw * rel_ned
        // First apply yaw
        Real64 y0 = cy * rel_n + sy * rel_e;
        Real64 y1 = -sy * rel_n + cy * rel_e;
        Real64 y2 = rel_d;

        // Then pitch
        Real64 p0 = cp * y0 - sp * y2;
        Real64 p1 = y1;
        Real64 p2 = sp * y0 + cp * y2;

        // Then roll
        Real64 x_body = p0;
        Real64 y_body = cr * p1 + sr * p2;
        Real64 z_body = -sr * p1 + cr * p2;

        Real64 azimuth = atan2(y_body, x_body);
        Real64 horiz = sqrt(x_body * x_body + y_body * y_body);
        Real64 elevation = atan2(-z_body, horiz);
        Real64 range = sqrt(x_body * x_body + y_body * y_body + z_body * z_body);

        z_out[0] = azimuth;
        z_out[1] = elevation;
        z_out[2] = range;
    }

    // ---- Ownship-induced noise via mini-UT ----
    bool UKF_base::compute_ownship_induced_noise(const Maverick::R64vector& intruder_state,
                                                 const Maverick::R64vector& ownship_pos,
                                                 const Maverick::R64vector& ownship_att,
                                                 const Maverick::R64matrix& ownship_cov,
                                                 Maverick::R64matrix& R_induced) const
    {
        const Uint32 dim_own = 6;
        const Uint32 n_sig_own = 2 * dim_own + 1;
        const Real64 kappa_own = 3.0 - static_cast<Real64>(dim_own);
        const Real64 lambda_own = alpha_ * alpha_ * (dim_own + kappa_own) - dim_own;

        Real64 own_mean[6];
        own_mean[0] = ownship_pos[0];
        own_mean[1] = ownship_pos[1];
        own_mean[2] = ownship_pos[2];
        own_mean[3] = ownship_att[0];
        own_mean[4] = ownship_att[1];
        own_mean[5] = ownship_att[2];

        // Generate ownship sigma points (n_sig_own x 6)
        Real64 own_sigmas[n_sig_own * 6];
        if (!generate_sigma_points(own_mean, ownship_cov, dim_own, own_sigmas, lambda_own))
        {
            return false;
        }

        // Weights for ownship mini-UT
        Real64 wm_own[n_sig_own];
        Real64 wc_own[n_sig_own];
        wm_own[0] = lambda_own / (dim_own + lambda_own);
        wc_own[0] = lambda_own / (dim_own + lambda_own) + (1.0 - alpha_ * alpha_ + beta_);
        const Real64 w_own = 1.0 / (2.0 * (dim_own + lambda_own));
        for (Uint32 i = 1; i < n_sig_own; ++i)
        {
            wm_own[i] = w_own;
            wc_own[i] = w_own;
        }

        // Transform each sigma through measurement function
        Real64 z_sigmas[n_sig_own * MAX_DIM_Z];
        for (Uint32 i = 0; i < n_sig_own; ++i)
        {
            Real64 s_pos[3] = {own_sigmas[i * 6 + 0], own_sigmas[i * 6 + 1], own_sigmas[i * 6 + 2]};
            Real64 s_att[3] = {own_sigmas[i * 6 + 3], own_sigmas[i * 6 + 4], own_sigmas[i * 6 + 5]};
            measurement_function(intruder_state.first(), s_pos, s_att, &z_sigmas[i * dim_z_]);
        }

        // Weighted mean (reference-point method for azimuth)
        Real64 z_mean[MAX_DIM_Z];
        memset(z_mean, 0, static_cast<size_t>(dim_z_) * sizeof(Real64));
        for (Uint32 j = 0; j < dim_z_; ++j)
        {
            for (Uint32 i = 0; i < n_sig_own; ++i)
            {
                z_mean[j] += wm_own[i] * z_sigmas[i * dim_z_ + j];
            }
        }
        // Fix azimuth mean via reference point
        Real64 az_ref = z_sigmas[0];  // central sigma azimuth
        Real64 az_sum = 0.0;
        for (Uint32 i = 0; i < n_sig_own; ++i)
        {
            az_sum += wm_own[i] * wrap_angle(z_sigmas[i * dim_z_] - az_ref);
        }
        z_mean[0] = az_ref + az_sum;

        // Compute R_induced = sum Wc_i * (z_i - z_mean)(z_i - z_mean)^T
        R_induced.zeros();
        for (Uint32 i = 0; i < n_sig_own; ++i)
        {
            Real64 dz[MAX_DIM_Z];
            for (Uint32 j = 0; j < dim_z_; ++j)
            {
                dz[j] = z_sigmas[i * dim_z_ + j] - z_mean[j];
            }
            dz[0] = wrap_angle(dz[0]);
            for (Uint32 r = 0; r < dim_z_; ++r)
            {
                for (Uint32 c = 0; c < dim_z_; ++c)
                {
                    R_induced.get_ij(r, c) += wc_own[i] * dz[r] * dz[c];
                }
            }
        }
        return true;
    }

    // ---- UKF measurement update (common to all models) ----
    void UKF_base::update(const Maverick::R64vector& z,
                          const Real64* meas_noise_std,
                          const Maverick::R64vector& ownship_pos,
                          const Maverick::R64vector& ownship_att,
                          const Maverick::R64matrix& ownship_cov)
    {
        // R_total = R + R_induced from ownship covariance.  R is built here
        // from the per-measurement noise std (its range term may scale with
        // the measured distance) rather than from a fixed member.
        Maverick::R64matrixn<MAX_DIM_Z> R_total;
        R_total.resize_mat(static_cast<Uint16>(dim_z_), static_cast<Uint16>(dim_z_));
        R_total.zeros();
        for (Uint32 d = 0; d < dim_z_; ++d)
        {
            R_total.get_ij(d, d) = meas_noise_std[d] * meas_noise_std[d];
        }
        {
            Maverick::R64matrixn<MAX_DIM_Z> R_geo;
            R_geo.resize_mat(static_cast<Uint16>(dim_z_), static_cast<Uint16>(dim_z_));
            R_geo.zeros();
            if (!compute_ownship_induced_noise(x_, ownship_pos, ownship_att, ownship_cov, R_geo))
            {
                return;  // Skip update on ill-conditioned ownship covariance
            }
            for (Uint32 r = 0; r < dim_z_; ++r)
            {
                for (Uint32 c = 0; c < dim_z_; ++c)
                {
                    R_total.get_ij(r, c) += R_geo.get_ij(r, c);
                }
            }
        }

        // Regenerate sigma points from current state
        if (!generate_sigma_points_state())
        {
            return;
        }

        // Transform sigma points through measurement model
        for (Uint32 i = 0; i < n_sigma_; ++i)
        {
            measurement_function(
                &sigma_pts_[i * dim_x_], ownship_pos.first(), ownship_att.first(), &sigma_z_[i * dim_z_]);
        }

        // Predicted measurement mean (reference-point azimuth)
        Real64 z_pred[MAX_DIM_Z];
        memset(z_pred, 0, static_cast<size_t>(dim_z_) * sizeof(Real64));
        for (Uint32 j = 0; j < dim_z_; ++j)
        {
            for (Uint32 i = 0; i < n_sigma_; ++i)
            {
                z_pred[j] += wm_[i] * sigma_z_[i * dim_z_ + j];
            }
        }
        Real64 az_ref = sigma_z_[0];
        Real64 az_sum = 0.0;
        for (Uint32 i = 0; i < n_sigma_; ++i)
        {
            az_sum += wm_[i] * wrap_angle(sigma_z_[i * dim_z_] - az_ref);
        }
        z_pred[0] = az_ref + az_sum;

        // Innovation covariance Pz = R_total + sum Wc * (dz)(dz)^T
        Maverick::R64matrixn<MAX_DIM_Z> Pz;
        Pz.resize_mat(static_cast<Uint16>(dim_z_), static_cast<Uint16>(dim_z_));
        for (Uint32 r = 0; r < dim_z_; ++r)
        {
            for (Uint32 c = 0; c < dim_z_; ++c)
            {
                Pz.get_ij(r, c) = R_total.get_ij(r, c);
            }
        }
        for (Uint32 i = 0; i < n_sigma_; ++i)
        {
            Real64 dz[MAX_DIM_Z];
            for (Uint32 j = 0; j < dim_z_; ++j)
            {
                dz[j] = sigma_z_[i * dim_z_ + j] - z_pred[j];
            }
            dz[0] = wrap_angle(dz[0]);
            for (Uint32 r = 0; r < dim_z_; ++r)
            {
                for (Uint32 c = 0; c < dim_z_; ++c)
                {
                    Pz.get_ij(r, c) += wc_[i] * dz[r] * dz[c];
                }
            }
        }

        // Cross-covariance Pxz = sum Wc * (dx)(dz)^T
        // dim_x × dim_z, stored via R64matrix wrapper on local buffer.
        Real64 Pxz_buf[MAX_DIM_X * MAX_DIM_Z];
        memset(Pxz_buf, 0, sizeof(Pxz_buf));
        Maverick::R64matrix Pxz(Pxz_buf, static_cast<Uint16>(dim_x_), static_cast<Uint16>(dim_z_));
        for (Uint32 i = 0; i < n_sigma_; ++i)
        {
            Real64 dx[MAX_DIM_X];
            for (Uint32 j = 0; j < dim_x_; ++j)
            {
                dx[j] = sigma_pts_[i * dim_x_ + j] - x_[j];
            }
            Real64 dz[MAX_DIM_Z];
            for (Uint32 j = 0; j < dim_z_; ++j)
            {
                dz[j] = sigma_z_[i * dim_z_ + j] - z_pred[j];
            }
            dz[0] = wrap_angle(dz[0]);
            for (Uint32 r = 0; r < dim_x_; ++r)
            {
                for (Uint32 c = 0; c < dim_z_; ++c)
                {
                    Pxz.get_ij(r, c) += wc_[i] * dx[r] * dz[c];
                }
            }
        }

        // K = Pxz * Pz^{-1}  via Cholesky solve: Pz * K^T = Pxz^T
        // Pz is symmetric so cholesky_decomp works directly.
        Maverick::R64matrixn<MAX_DIM_Z> Pz_chol;
        Pz_chol.resize_mat(static_cast<Uint16>(dim_z_), static_cast<Uint16>(dim_z_));
        for (Uint32 r = 0; r < dim_z_; ++r)
        {
            for (Uint32 c = 0; c < dim_z_; ++c)
            {
                Pz_chol.get_ij(r, c) = Pz.get_ij(r, c);
            }
        }
        if (!Pz_chol.cholesky_decomp())
        {
            return;  // Skip update on singular Pz
        }

        // Solve Pz * K^T[:,col] = Pxz[col,:] for each state dimension
        Real64 K_buf[MAX_DIM_X * MAX_DIM_Z];
        memset(K_buf, 0, sizeof(K_buf));
        Maverick::R64matrix K(K_buf, static_cast<Uint16>(dim_x_), static_cast<Uint16>(dim_z_));
        Real64 b_buf[MAX_DIM_Z];
        Real64 x_buf[MAX_DIM_Z];
        Maverick::R64vector b_vec(b_buf, static_cast<Uint16>(dim_z_));
        Maverick::R64vector x_vec(x_buf, static_cast<Uint16>(dim_z_));
        for (Uint32 col = 0; col < dim_x_; ++col)
        {
            for (Uint32 r = 0; r < dim_z_; ++r)
            {
                b_buf[r] = Pxz.get_ij(col, r);
            }
            Pz_chol.cholesky_solve(b_vec, x_vec);
            for (Uint32 r = 0; r < dim_z_; ++r)
            {
                K.get_ij(col, r) = x_buf[r];
            }
        }

        // Innovation
        Real64 innov[MAX_DIM_Z];
        for (Uint32 i = 0; i < dim_z_; ++i)
        {
            innov[i] = z[i] - z_pred[i];
        }
        innov[0] = wrap_angle(innov[0]);

        // x = x + K * innovation
        for (Uint32 i = 0; i < dim_x_; ++i)
        {
            Real64 ki = 0.0;
            for (Uint32 j = 0; j < dim_z_; ++j)
            {
                ki += K.get_ij(i, j) * innov[j];
            }
            x_[i] += ki;
        }

        // P = P - K * Pz * K^T
        // tmp = K * Pz  (dim_x x dim_z)
        Real64 tmp_buf[MAX_DIM_X * MAX_DIM_Z];
        Maverick::R64matrix tmp(tmp_buf, static_cast<Uint16>(dim_x_), static_cast<Uint16>(dim_z_));
        for (Uint32 i = 0; i < dim_x_; ++i)
        {
            for (Uint32 j = 0; j < dim_z_; ++j)
            {
                Real64 s = 0.0;
                for (Uint32 k = 0; k < dim_z_; ++k)
                {
                    s += K.get_ij(i, k) * Pz.get_ij(k, j);
                }
                tmp.get_ij(i, j) = s;
            }
        }
        // P -= tmp * K^T
        for (Uint32 i = 0; i < dim_x_; ++i)
        {
            for (Uint32 j = 0; j < dim_x_; ++j)
            {
                Real64 s = 0.0;
                for (Uint32 k = 0; k < dim_z_; ++k)
                {
                    s += tmp.get_ij(i, k) * K.get_ij(j, k);
                }
                P_.get_ij(i, j) -= s;
            }
        }

        // Force symmetry
        for (Uint32 i = 0; i < dim_x_; ++i)
        {
            for (Uint32 j = i + 1; j < dim_x_; ++j)
            {
                Real64 avg = 0.5 * (P_.get_ij(i, j) + P_.get_ij(j, i));
                P_.get_ij(i, j) = avg;
                P_.get_ij(j, i) = avg;
            }
        }
    }

}  // namespace DAA
