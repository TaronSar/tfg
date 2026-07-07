// ---------------------------------------------------------------
// DAA_dll.cpp — DLL glue: thin extern "C" wrappers around
//               DAA::DAA_simulator (route follower + embedded CV-UKF
//               intruder tracker).
//
// Each simulation thread creates its own Daa_simulator handle.
// No shared mutable state — thread-safe by design.
// ---------------------------------------------------------------

#define DAA_DLL_BUILD
#include <DAA_dll.h>
#include <DAA_simulator.h>
#include <cstdlib>
#include <cmath>
#include <new>

extern "C" {

// ---------------------------------------------------------------
// Route-following simulator — opaque handle wrapping DAA::DAA_simulator.
//
// The wrapper also owns the embedded estimator's propagation output
// buffers (and a scratch trajectory buffer for fused scoring without a
// caller buffer), sized once at construction from the look-ahead
// horizon and step.  DAA::DAA_simulator stays allocation-free; all the
// dynamic memory lives here.
//
// Placement new + explicit destructor + malloc/free avoid pulling in
// C++ exception handling (libgcc_eh) from operator new/delete.
// ---------------------------------------------------------------
struct Daa_simulator
{
    DAA::DAA_simulator impl;
    int     cap;       // number of propagation samples
    double  dt;        // step (s)
    double* pos_buf;   // [cap * 3]
    double* cov_buf;   // [cap * 4]  packed {Pnn,Pne,Pee,Pdd} per sample
    double* traj_buf;  // [cap * 3] scratch for fused scoring

    explicit Daa_simulator(const DAA::DAA_simulator_cfg& cfg)
        : impl(cfg), cap(0), dt(0.0),
          pos_buf(0), cov_buf(0), traj_buf(0) {}
};

DAA_EXPORT Daa_simulator* daa_sim_create(
    double dt,
    double sim_dt_max,
    double k_xt,
    const double* p0_ned,
    const double* v0_ned,
    int route_capacity,
    double a_max_along,
    double rate_max_azimuth,
    double rate_max_elevation,
    double v_max,
    double v_min,
    double el_min,
    double el_max,
    double lookahead,
    double ukf_alpha,
    double ukf_beta,
    double ukf_kappa,
    double cyl_h,
    double cyl_d,
    int ukf_model)
{
    if (p0_ned == 0 || v0_ned == 0 || route_capacity <= 0) { return 0; }
    if (dt <= 0.0 || lookahead < 0.0) { return 0; }
    int cap = (int)ceil(lookahead / dt + 0.5);
    if (cap < 1) { cap = 1; }
    DAA::DAA_simulator_cfg cfg;
    cfg.dt             = dt;
    cfg.lookahead      = 0U;
    cfg.sim_dt_max     = sim_dt_max;
    cfg.k_xt           = k_xt;
    cfg.p0_ned[0]      = p0_ned[0];
    cfg.p0_ned[1]      = p0_ned[1];
    cfg.p0_ned[2]      = p0_ned[2];
    cfg.v0_ned[0]      = v0_ned[0];
    cfg.v0_ned[1]      = v0_ned[1];
    cfg.v0_ned[2]      = v0_ned[2];
    cfg.route_capacity = static_cast<unsigned int>(route_capacity);
    cfg.env.a_max_along            = a_max_along;
    cfg.env.rate_max_azimuth       = rate_max_azimuth;
    cfg.env.rate_max_elevation     = rate_max_elevation;
    cfg.env.v_max  = v_max;
    cfg.env.v_min  = v_min;
    cfg.env.el_min = el_min;
    cfg.env.el_max = el_max;
    cfg.ukf_alpha      = ukf_alpha;
    cfg.ukf_beta       = ukf_beta;
    cfg.ukf_kappa      = ukf_kappa;
    cfg.cyl_h          = cyl_h;
    cfg.cyl_d          = cyl_d;
    switch (ukf_model)
    {
        case 1:  cfg.ukf_model = DAA::UKF_MODEL_CA;   break;
        case 2:  cfg.ukf_model = DAA::UKF_MODEL_CAB;  break;
        case 3:  cfg.ukf_model = DAA::UKF_MODEL_CTRA; break;
        default: cfg.ukf_model = DAA::UKF_MODEL_CV;   break;
    }
    void* mem = malloc(sizeof(Daa_simulator));
    if (mem == 0) { return 0; }
    Daa_simulator* sim = new(mem) Daa_simulator(cfg);
    sim->cap      = cap;
    sim->dt       = dt;
    sim->pos_buf  = (double*)malloc((size_t)cap * 3 * sizeof(double));
    sim->cov_buf  = (double*)malloc((size_t)cap * 4 * sizeof(double));
    sim->traj_buf = (double*)malloc((size_t)cap * 3 * sizeof(double));
    if (sim->pos_buf == 0
        || sim->cov_buf == 0 || sim->traj_buf == 0)
    {
        free(sim->pos_buf);
        free(sim->cov_buf);
        free(sim->traj_buf);
        sim->~Daa_simulator();
        free(sim);
        return 0;
    }
    return sim;
}

DAA_EXPORT void daa_sim_destroy(Daa_simulator* sim)
{
    if (sim != 0)
    {
        free(sim->pos_buf);
        free(sim->cov_buf);
        free(sim->traj_buf);
        sim->~Daa_simulator();
        free(sim);
    }
}

DAA_EXPORT int daa_sim_push_route(Daa_simulator* sim,
                                  const double* pdt_n4,
                                  int n)
{
    if (sim == 0 || pdt_n4 == 0 || n < 0) { return -1; }
    const unsigned int pushed = sim->impl.push_route(
        pdt_n4, static_cast<unsigned int>(n));
    return static_cast<int>(pushed);
}

// Translate the flat C route-transform arguments into a
// DAA::Route_transform.  ``mode`` selects the guidance law:
//   0 = track route (shift3 + speed_scale),
//   1 = hold velocity (vel3),
//   2 = external track (straight track_p0 -> track_p1 segment).
// Any pointer argument may be NULL (treated as the zero vector).
static void fill_route_xf(DAA::Route_transform& xf,
                          int mode,
                          const double* shift3,
                          double speed_scale,
                          const double* vel3,
                          const double* track_p0,
                          const double* track_p1,
                          double track_speed)
{
    if (mode == 1)      { xf.mode = DAA::GUIDANCE_HOLD_VELOCITY; }
    else if (mode == 2) { xf.mode = DAA::GUIDANCE_EXTERNAL_TRACK; }
    else                { xf.mode = DAA::GUIDANCE_TRACK_ROUTE; }
    xf.shift[0] = (shift3 != 0) ? shift3[0] : 0.0;
    xf.shift[1] = (shift3 != 0) ? shift3[1] : 0.0;
    xf.shift[2] = (shift3 != 0) ? shift3[2] : 0.0;
    xf.speed_scale = speed_scale;
    xf.velocity[0] = (vel3 != 0) ? vel3[0] : 0.0;
    xf.velocity[1] = (vel3 != 0) ? vel3[1] : 0.0;
    xf.velocity[2] = (vel3 != 0) ? vel3[2] : 0.0;
    xf.track_p0[0] = (track_p0 != 0) ? track_p0[0] : 0.0;
    xf.track_p0[1] = (track_p0 != 0) ? track_p0[1] : 0.0;
    xf.track_p0[2] = (track_p0 != 0) ? track_p0[2] : 0.0;
    xf.track_p1[0] = (track_p1 != 0) ? track_p1[0] : 0.0;
    xf.track_p1[1] = (track_p1 != 0) ? track_p1[1] : 0.0;
    xf.track_p1[2] = (track_p1 != 0) ? track_p1[2] : 0.0;
    xf.track_speed = track_speed;
}

DAA_EXPORT int daa_sim_set_route_xf(Daa_simulator* sim,
                                    int mode,
                                    const double* shift3,
                                    double speed_scale,
                                    const double* vel3,
                                    const double* track_p0,
                                    const double* track_p1,
                                    double track_speed)
{
    if (sim == 0) { return -1; }
    DAA::Route_transform xf;
    fill_route_xf(xf, mode, shift3, speed_scale, vel3, track_p0, track_p1,
                  track_speed);
    sim->impl.set_route_xf(xf);
    return 0;
}

DAA_EXPORT int daa_sim_get_route_xf(const Daa_simulator* sim,
                                    int* mode_out,
                                    double* shift3_out,
                                    double* speed_scale_out,
                                    double* vel3_out,
                                    double* track_p0_out,
                                    double* track_p1_out,
                                    double* track_speed_out)
{
    if (sim == 0) { return -1; }
    const DAA::Route_transform& xf = sim->impl.route_xf();
    if (mode_out != 0) { *mode_out = static_cast<int>(xf.mode); }
    if (shift3_out != 0)
    {
        shift3_out[0] = xf.shift[0];
        shift3_out[1] = xf.shift[1];
        shift3_out[2] = xf.shift[2];
    }
    if (speed_scale_out != 0) { *speed_scale_out = xf.speed_scale; }
    if (vel3_out != 0)
    {
        vel3_out[0] = xf.velocity[0];
        vel3_out[1] = xf.velocity[1];
        vel3_out[2] = xf.velocity[2];
    }
    if (track_p0_out != 0)
    {
        track_p0_out[0] = xf.track_p0[0];
        track_p0_out[1] = xf.track_p0[1];
        track_p0_out[2] = xf.track_p0[2];
    }
    if (track_p1_out != 0)
    {
        track_p1_out[0] = xf.track_p1[0];
        track_p1_out[1] = xf.track_p1[1];
        track_p1_out[2] = xf.track_p1[2];
    }
    if (track_speed_out != 0) { *track_speed_out = xf.track_speed; }
    return 0;
}

DAA_EXPORT int daa_sim_get_position(const Daa_simulator* sim,
                                    double* p_out)
{
    if (sim == 0 || p_out == 0) { return -1; }
    sim->impl.get_position(p_out);
    return 0;
}

DAA_EXPORT int daa_sim_get_velocity(const Daa_simulator* sim,
                                    double* v_out)
{
    if (sim == 0 || v_out == 0) { return -1; }
    sim->impl.get_velocity(v_out);
    return 0;
}

DAA_EXPORT int daa_sim_step(Daa_simulator* sim,
                            double* p_out,
                            double* v_out,
                            double* track_pt_out)
{
    if (sim == 0) { return -1; }
    sim->impl.step(p_out, v_out, track_pt_out);
    return 0;
}

DAA_EXPORT int daa_sim_simulate(const Daa_simulator* sim,
                                int mode,
                                const double* shift3,
                                double speed_scale,
                                const double* vel3,
                                const double* track_p0,
                                const double* track_p1,
                                double track_speed,
                                double* traj_out,
                                int n_out)
{
    if (sim == 0 || traj_out == 0 || n_out <= 0) { return -1; }
    DAA::Route_transform xf;
    fill_route_xf(xf, mode, shift3, speed_scale, vel3, track_p0, track_p1,
                  track_speed);
    sim->impl.simulate(xf, traj_out, static_cast<unsigned int>(n_out));
    return 0;
}

DAA_EXPORT int daa_sim_est_init_from_measurement(Daa_simulator* sim,
    const double* z,
    const double* ownship_pos,
    const double* ownship_att,
    const double* ownship_cov,
    double dt,
    double process_noise_std,
    const double* meas_noise_std,
    double velocity_var,
    double acceleration_var,
    double velocity_var_vertical,
    double acceleration_var_vertical,
    const double* q_var_diag,
    int q_n)
{
    if (sim == 0 || z == 0 || ownship_pos == 0 || ownship_att == 0
        || ownship_cov == 0 || meas_noise_std == 0) { return -1; }
    if (q_n < 0) { return -2; }
    sim->impl.est_initialize_from_measurement(z, ownship_pos, ownship_att,
                                              ownship_cov, dt,
                                              process_noise_std,
                                              meas_noise_std, velocity_var,
                                              acceleration_var,
                                              velocity_var_vertical,
                                              acceleration_var_vertical,
                                              q_var_diag,
                                              (unsigned int)q_n);
    return 0;
}

DAA_EXPORT int daa_sim_est_predict(Daa_simulator* sim)
{
    if (sim == 0) { return -1; }
    sim->impl.est_predict();
    return 0;
}

DAA_EXPORT int daa_sim_est_update(Daa_simulator* sim,
    const double* z,
    const double* meas_noise_std,
    const double* ownship_pos,
    const double* ownship_att,
    const double* ownship_cov)
{
    if (sim == 0 || z == 0 || meas_noise_std == 0 || ownship_pos == 0
        || ownship_att == 0 || ownship_cov == 0) { return -1; }
    sim->impl.est_update(z, meas_noise_std, ownship_pos, ownship_att, ownship_cov);
    return 0;
}

DAA_EXPORT int daa_sim_est_get_state(const Daa_simulator* sim,
    double* state6_out,
    double* P36_out,
    double* accel_var3_out)
{
    if (sim == 0) { return -1; }
    sim->impl.est_get_state(state6_out, P36_out, accel_var3_out);
    return 0;
}

DAA_EXPORT int daa_sim_propagate_batch(Daa_simulator* sim, int n)
{
    if (sim == 0) { return -1; }
    if (n < 0 || n > sim->cap) { return -2; }
    sim->impl.est_propagate_batch(n, sim->pos_buf, sim->cov_buf);
    return 0;
}

DAA_EXPORT int daa_sim_capacity(const Daa_simulator* sim)
{
    return (sim == 0) ? -1 : sim->cap;
}

DAA_EXPORT const double* daa_sim_propagation_pos(const Daa_simulator* sim)
{
    return (sim == 0) ? 0 : sim->pos_buf;
}

DAA_EXPORT const double* daa_sim_propagation_cov(const Daa_simulator* sim)
{
    return (sim == 0) ? 0 : sim->cov_buf;
}

DAA_EXPORT double daa_sim_simulate_and_score(Daa_simulator* sim,
    int mode,
    const double* shift3,
    double speed_scale,
    const double* vel3,
    const double* track_p0,
    const double* track_p1,
    double track_speed,
    double* traj_out,
    int n_out,
    int* idx_cpa_out)
{
    if (sim == 0 || n_out <= 0 || n_out > sim->cap) { return -1.0; }
    DAA::Route_transform xf;
    fill_route_xf(xf, mode, shift3, speed_scale, vel3, track_p0, track_p1,
                  track_speed);
    // Project into the caller's buffer when given, otherwise the
    // owned scratch buffer (the projection is then discarded).
    double* traj = (traj_out != 0) ? traj_out : sim->traj_buf;
    return sim->impl.simulate_and_score(
        xf, traj, static_cast<unsigned int>(n_out),
        sim->pos_buf, sim->cov_buf, idx_cpa_out);
}
} // extern "C"
