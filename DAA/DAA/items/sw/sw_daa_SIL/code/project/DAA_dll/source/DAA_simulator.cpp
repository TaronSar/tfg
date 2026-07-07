// ---------------------------------------------------------------
// DAA_simulator.cpp — implementation of DAA::DAA_simulator.
// ---------------------------------------------------------------
#include <DAA_simulator.h>

#include <Route_cursor.h>
#include <Route_simulator.h>
#include <cstring>

namespace DAA
{

    DAA_simulator::DAA_simulator(const DAA_simulator_cfg& cfg) :
            cfg_(cfg),
            route_(cfg.route_capacity),
            own_(),
            current_route_xf_(),
            estimator_cv_(),
            estimator_ca_(),
            estimator_cab_(),
            estimator_ctra_(),
            estimator_(0)
    {
        // Seed the ownship kinematic state and envelope.
        own_.set_position(cfg_.p0_ned);
        own_.set_velocity(cfg_.v0_ned);
        own_.set_envelope(cfg_.env);

        // Select the concrete estimator for the configured motion
        // model; all three are held in-object so this is just a
        // pointer assignment (no dynamic allocation).  CV is the
        // default for any unrecognised value.
        switch (cfg_.ukf_model)
        {
            case UKF_MODEL_CA:   estimator_ = &estimator_ca_;   break;
            case UKF_MODEL_CAB:  estimator_ = &estimator_cab_;  break;
            case UKF_MODEL_CTRA: estimator_ = &estimator_ctra_; break;
            case UKF_MODEL_CV:
            default:             estimator_ = &estimator_cv_;   break;
        }

        // Configure the embedded intruder estimator's sigma-point
        // weighting; state/covariance are seeded later via
        // est_initialize() on first sighting.
        estimator_->set_ukf_params(cfg_.ukf_alpha, cfg_.ukf_beta,
                                   cfg_.ukf_kappa);
    }

    DAA_simulator::~DAA_simulator()
    {
    }

    Uint32 DAA_simulator::push_route(const Real64* pdt_n4, Uint32 n)
    {
        return route_.push_batch(pdt_n4, n);
    }

    void DAA_simulator::set_route_xf(const Route_transform& xf)
    {
        current_route_xf_ = xf;
    }

    const Route_transform& DAA_simulator::route_xf() const
    {
        return current_route_xf_;
    }

    void DAA_simulator::get_position(Real64* p_out) const
    {
        own_.get_position(p_out);
    }

    void DAA_simulator::get_velocity(Real64* v_out) const
    {
        own_.get_velocity(v_out);
    }

    void DAA_simulator::step(Real64* p_out,
                             Real64* v_out,
                             Real64* track_pt_out)
    {
        // Integrate forward by cfg.dt in fixed-ish sub-steps under the
        // current route transform.  A fresh cursor starts at the
        // tracker head, which pop_to_cursor() keeps current by popping
        // surpassed waypoints after each step.
        Route_cursor cursor = route_.make_cursor();
        simulate_route_advance(cursor, current_route_xf_, cfg_.k_xt,
                               cfg_.dt, cfg_.sim_dt_max, own_);

        // Pop every waypoint the cursor advanced past so the tracker
        // head is realigned with the cursor's active segment.
        route_.pop_to_cursor(cursor);

        // Report the per-step quantities the caller asked for.
        Real64 p_now[3];
        own_.get_position(p_now);
        if (p_out != 0)
        {
            p_out[0] = p_now[0];
            p_out[1] = p_now[1];
            p_out[2] = p_now[2];
        }
        if (v_out != 0)
        {
            own_.get_velocity(v_out);
        }
        if (track_pt_out != 0)
        {
            // Foot of perpendicular on the active route segment; when
            // the route is exhausted fall back to the current position.
            if (!route_.project_active(p_now, track_pt_out))
            {
                track_pt_out[0] = p_now[0];
                track_pt_out[1] = p_now[1];
                track_pt_out[2] = p_now[2];
            }
        }
    }

    void DAA_simulator::simulate(const Route_transform& route_xf,
                                 Real64* traj_out,
                                 Uint32 n_out) const
    {
        if ((traj_out != 0) && (n_out != 0U))
        {
            // Project on a private ownship copy so this simulator and
            // its tracker are left untouched.
            Virtual_ownship own;
            own.set_envelope(cfg_.env);
            Real64 p[3];
            Real64 v[3];
            own_.get_position(p);
            own_.get_velocity(v);
            own.set_position(p);
            own.set_velocity(v);

            // First sample = current position.
            traj_out[0] = p[0];
            traj_out[1] = p[1];
            traj_out[2] = p[2];

            // One cursor reused across the whole projection so segment
            // progress stays monotonic even when the route loops back.
            Route_cursor cursor = route_.make_cursor();

            // Each subsequent sample advances the projection by cfg.dt
            // and is written straight into the output slice.
            const Real64* const out_z = traj_out + (3U * n_out);
            for (Real64* out = traj_out + 3U; out < out_z; out += 3)
            {
                simulate_route_advance(cursor, route_xf, cfg_.k_xt,
                                       cfg_.dt, cfg_.sim_dt_max, own);
                own.get_position(out);
            }
        }
    }

    void DAA_simulator::est_initialize_from_measurement(const Real64* z,
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
        estimator_->initialize_from_measurement(z, ownship_pos, ownship_att,
                                                ownship_cov, dt,
                                                process_noise_std,
                                                meas_noise_std, velocity_var,
                                                acceleration_var,
                                                velocity_var_vertical,
                                                acceleration_var_vertical,
                                                q_var_diag, q_n);
    }

    void DAA_simulator::est_predict()
    {
        estimator_->predict();
    }

    void DAA_simulator::est_update(const Real64* z,
                                   const Real64* meas_noise_std,
                                   const Real64* ownship_pos,
                                   const Real64* ownship_att,
                                   const Real64* ownship_cov)
    {
        estimator_->update(
            Maverick::R64vector::K(z, 3).kvec,
            meas_noise_std,
            Maverick::R64vector::K(ownship_pos, 3).kvec,
            Maverick::R64vector::K(ownship_att, 3).kvec,
            Maverick::R64matrix::K(ownship_cov, 6, 6).kmat);
    }

    void DAA_simulator::est_get_state(Real64* state6_out,
                                      Real64* cov36_out,
                                      Real64* accel_var3_out) const
    {
        // All motion models store [n, e, d, vn, ve, vd] as their first
        // six state components, so the position/velocity slice is the
        // same regardless of the model's full dimension.
        if (state6_out != 0)
        {
            memcpy(state6_out, estimator_->state().first(),
                   6U * sizeof(Real64));
        }
        if (cov36_out != 0)
        {
            // Copy the 6x6 position/velocity block element-wise.  The
            // full covariance may be larger than 6x6 (CA/CAB are 9x9)
            // and is column-major, so a flat memcpy of the first 36
            // values would not be the wanted sub-block.  The matrix is
            // symmetric, so the row-major output matches either order.
            const Maverick::R64matrix& P = estimator_->covariance();
            for (Uint32 r = 0U; r < 6U; ++r)
            {
                for (Uint32 c = 0U; c < 6U; ++c)
                {
                    cov36_out[(r * 6U) + c] = P.get_ij(r, c);
                }
            }
        }
        if (accel_var3_out != 0)
        {
            // Diagonal variances of the acceleration states (indices
            // 6, 7, 8 for the CA / CAB models).  Models without an
            // acceleration state (CV, dim_x = 6) report zero.
            if (estimator_->dim_x() >= 9U)
            {
                const Maverick::R64matrix& P = estimator_->covariance();
                accel_var3_out[0] = P.get_ij(6U, 6U);
                accel_var3_out[1] = P.get_ij(7U, 7U);
                accel_var3_out[2] = P.get_ij(8U, 8U);
            }
            else if (estimator_->dim_x() == 8U)
            {
                // CTRA (8-state): index 6 = tangential acceleration
                // variance, index 7 = turn-rate variance.  There is no
                // third manoeuvre state, so the last slot reports zero.
                const Maverick::R64matrix& P = estimator_->covariance();
                accel_var3_out[0] = P.get_ij(6U, 6U);
                accel_var3_out[1] = P.get_ij(7U, 7U);
                accel_var3_out[2] = 0.0;
            }
            else
            {
                accel_var3_out[0] = 0.0;
                accel_var3_out[1] = 0.0;
                accel_var3_out[2] = 0.0;
            }
        }
    }

    void DAA_simulator::est_propagate_batch(int n,
                                            Real64* pos_out,
                                            Real64* cov_out) const
    {
        // Propagate on the uniform grid i*dt using the configured step.
        estimator_->propagate_batch(cfg_.dt, static_cast<Uint32>(n),
                                    pos_out, cov_out);
    }

    Real64 DAA_simulator::simulate_and_score(const Route_transform& route_xf,
                                             Real64* traj_out,
                                             Uint32 n_out,
                                             const Real64* int_pos,
                                             const Real64* int_cov,
                                             int* idx_cpa_out) const
    {
        // Project the look-ahead trajectory, then score it against the
        // supplied propagated intruder track in a single call so the
        // caller pays only one boundary crossing.  The protection
        // cylinder dimensions come from the simulator configuration.
        simulate(route_xf, traj_out, n_out);
        int idx_cpa = -1;
        const Real64 d = estimator_->min_1sigma_cylinder_distance(
            traj_out, int_pos, int_cov, static_cast<int>(n_out),
            cfg_.cyl_h, cfg_.cyl_d, &idx_cpa);
        if (idx_cpa_out != 0)
        {
            *idx_cpa_out = idx_cpa;
        }
        return d;
    }

}  // namespace DAA
