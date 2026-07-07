// ---------------------------------------------------------------
// DAA_dll.h — Public C API for the DAA route-following simulator
//             (handle-based) with an embedded CV-UKF intruder tracker.
// ---------------------------------------------------------------
#ifndef DAA_DLL_H
#define DAA_DLL_H

#ifdef _WIN32
    #ifdef DAA_DLL_BUILD
        #define DAA_EXPORT __declspec(dllexport)
    #else
        #define DAA_EXPORT __declspec(dllimport)
    #endif
#else
    #define DAA_EXPORT __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
extern "C" {
#endif

// ---- Route-following simulator (stateful) --------------------

/// Opaque handle wrapping DAA::DAA_simulator (per-thread).  Owns a
/// Route_tracker (the route to fly), a Virtual_ownship (flight
/// state) and a current Route_transform (affine shift + dt scale
/// applied to the route on the fly, initially the identity).
typedef struct Daa_simulator Daa_simulator;

/// Create a simulator.
///
/// @param dt              Real-flight step duration (s) for daa_sim_step.
/// @param sim_dt_max      Maximum integration sub-step (s).
/// @param k_xt            Cross-track line-attraction gain (1/m, = 1/look-ahead).
/// @param p0_ned          [3] initial ownship NED position (ft).
/// @param v0_ned          [3] initial ownship NED velocity (ft/s).
/// @param route_capacity  Waypoint capacity of the internal tracker
///                        (>= 2 recommended).
/// @param a_max_along        Speed-module (along-track) accel limit (m/s^2).
/// @param rate_max_azimuth   Course-angle (azimuth) rate limit (rad/s).
/// @param rate_max_elevation Flight-path-angle (elevation) rate limit (rad/s).
/// @param v_max   Upper bound on the speed module |v| (m/s).
/// @param v_min   Lower bound on the speed module |v| (m/s, stall guard).
/// @param el_min  Min flight-path angle (rad, descent, negative).
/// @param el_max  Max flight-path angle (rad, climb, positive).
/// @param lookahead       Look-ahead horizon (s) that sizes the embedded
///                        estimator's propagation buffers
///                        (cap = ceil(lookahead/dt + 0.5)).
/// @param ukf_alpha       UKF sigma-point spread parameter.
/// @param ukf_beta        UKF distribution prior parameter.
/// @param ukf_kappa       UKF secondary scaling parameter.
/// @param cyl_h           Protection cylinder half-height (ft) used by
///                        daa_sim_simulate_and_score.
/// @param cyl_d           Protection cylinder diameter (ft) used by
///                        daa_sim_simulate_and_score.
/// @param ukf_model       Embedded intruder estimator motion model:
///                        0 = constant-velocity, 1 = constant-accel (NED),
///                        2 = constant-accel (body).  Out-of-range values
///                        fall back to constant-velocity.
/// @return Handle, or NULL on allocation failure / bad-arg.
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
    int ukf_model);

/// Destroy the simulator and free its memory.  Safe to call with NULL.
DAA_EXPORT void daa_sim_destroy(Daa_simulator* sim);

/// Append N waypoints to the route from a row-major (N x 4) array
/// where each row is [N, E, D, speed] (NED m + per-segment target
/// speed m/s).  The speed in row i is the speed the ownship shall have
/// when flying *towards* waypoint i, so the first row's speed is unused.
/// @return Number of waypoints actually pushed (< N if the tracker
///         capacity is reached), or -1 on bad-arg.
DAA_EXPORT int  daa_sim_push_route(Daa_simulator* sim,
                                   const double* pdt_n4,
                                   int n);

/// Replace the active route transform (guidance modifier).
/// @param mode     Guidance mode: 0 = track route, 1 = hold velocity,
///                 2 = external track (straight track_p0 -> track_p1).
/// @param shift3   [3] NED position increment added to every waypoint
///                 (used when @p mode is 0; may be NULL to mean zero).
/// @param speed_scale Multiplier applied to every segment target speed
///                 (used when @p mode is 0).
/// @param vel3     [3] NED velocity to hold (used when @p mode is 1;
///                 may be NULL to mean zero).
/// @param track_p0 [3] NED segment start (used when @p mode is 2;
///                 may be NULL to mean zero).
/// @param track_p1 [3] NED segment end (used when @p mode is 2;
///                 may be NULL to mean zero).
/// @param track_speed Constant segment speed in m/s (used when @p mode
///                 is 2).
DAA_EXPORT int  daa_sim_set_route_xf(Daa_simulator* sim,
                                     int mode,
                                     const double* shift3,
                                     double speed_scale,
                                     const double* vel3,
                                     const double* track_p0,
                                     const double* track_p1,
                                     double track_speed);

/// Copy out the active route transform.  Any output pointer may be NULL.
/// @param mode_out      receives the guidance mode (0, 1 or 2).
/// @param shift3_out    [3] receives the NED shift.
/// @param speed_scale_out  receives the segment target-speed scale.
/// @param vel3_out      [3] receives the held NED velocity.
/// @param track_p0_out  [3] receives the external-track segment start.
/// @param track_p1_out  [3] receives the external-track segment end.
/// @param track_speed_out receives the external-track segment speed.
DAA_EXPORT int  daa_sim_get_route_xf(const Daa_simulator* sim,
                                     int* mode_out,
                                     double* shift3_out,
                                     double* speed_scale_out,
                                     double* vel3_out,
                                     double* track_p0_out,
                                     double* track_p1_out,
                                     double* track_speed_out);

/// Copy out the current ownship NED position (3 doubles).
DAA_EXPORT int  daa_sim_get_position(const Daa_simulator* sim,
                                     double* p_out);

/// Copy out the current ownship NED velocity (3 doubles).
DAA_EXPORT int  daa_sim_get_velocity(const Daa_simulator* sim,
                                     double* v_out);

/// Advance the real flight by dt under the current route transform
/// (sub-stepped at sim_dt_max) and pop every surpassed waypoint from
/// the tracker.  The per-step quantities are reported through the
/// optional output pointers (any may be NULL to skip):
///   @param p_out        [3] new ownship NED position (ft).
///   @param v_out        [3] new ownship NED velocity (ft/s).
///   @param track_pt_out [3] foot of perpendicular of the new position
///                       onto the active route segment (NED ft).
DAA_EXPORT int  daa_sim_step(Daa_simulator* sim,
                             double* p_out,
                             double* v_out,
                             double* track_pt_out);

/// Project the look-ahead trajectory the ownship would fly from its
/// current state under a hypothetical route transform, without
/// modifying the simulator or its tracker.  Samples are spaced dt
/// apart in time; traj_out[0] is the current position.
///
/// @param mode     Guidance mode: 0 = track route, 1 = hold velocity,
///                 2 = external track (straight track_p0 -> track_p1).
/// @param shift3   [3] NED shift of the hypothetical transform
///                 (used when @p mode is 0; may be NULL to mean zero).
/// @param speed_scale Segment target-speed scale of the hypothetical
///                 transform (mode 0).
/// @param vel3     [3] NED velocity to hold (used when @p mode is 1;
///                 may be NULL to mean zero).
/// @param track_p0 [3] NED segment start (used when @p mode is 2).
/// @param track_p1 [3] NED segment end (used when @p mode is 2).
/// @param track_speed Constant segment speed in m/s (used when @p mode
///                 is 2).
/// @param traj_out [n_out x 3] row-major NED positions (m).
/// @param n_out    Number of samples to write (>= 1).
DAA_EXPORT int  daa_sim_simulate(const Daa_simulator* sim,
                                 int mode,
                                 const double* shift3,
                                 double speed_scale,
                                 const double* vel3,
                                 const double* track_p0,
                                 const double* track_p1,
                                 double track_speed,
                                 double* traj_out,
                                 int n_out);

// ---- Embedded intruder estimator (CV UKF) --------------------
// The simulator owns a constant-velocity UKF tracking the intruder
// plus its propagation output buffers, sized at creation from the
// look-ahead horizon and step.  This lets the caller score a projected
// look-ahead trajectory against the propagated intruder track in a
// single boundary crossing (daa_sim_simulate_and_score).

/// Initialise the embedded estimator from a single first measurement.
/// The intruder position and an anisotropic initial position covariance
/// are derived from the measurement geometry inside the estimator;
/// velocity / acceleration are seeded to zero with the supplied
/// variances and refined by the subsequent predict/update stream.
/// @param z                 [3] measurement {az_rad, el_rad, range_ft}.
/// @param ownship_pos       [3] ownship NED position (ft).
/// @param ownship_att       [3] ownship attitude (rad).
/// @param ownship_cov       [6x6] row-major ownship state covariance.
/// @param dt                Filter time step (s).
/// @param process_noise_std Process noise standard deviation.
/// @param meas_noise_std    [3] measurement noise std {az, el, range}.
/// @param velocity_var      Initial horizontal velocity variance ((ft/s)^2).
/// @param acceleration_var  Initial horizontal acceleration variance ((ft/s^2)^2);
///                          ignored by models without an acceleration state.
/// @param velocity_var_vertical     Initial vertical (down) velocity variance
///                          ((ft/s)^2); tighter than horizontal as aircraft fly level.
/// @param acceleration_var_vertical Initial vertical (down) acceleration variance
///                          ((ft/s^2)^2); ignored by models without an accel state.
/// @param q_var_diag        Optional [q_n] per-state process-noise variance
///                          diagonal (state order).  When non-NULL and @p q_n
///                          equals the model's state dimension (6 CV, 9 CA/CAB,
///                          8 CTRA) it overrides Q's diagonal so each manoeuvre
///                          channel is tuned independently — needed for CTRA,
///                          whose tangential-acceleration ((ft/s^2)^2) and
///                          turn-rate ((rad/s)^2) channels need very different
///                          magnitudes.  NULL keeps the model's own (possibly
///                          structured) Q built from @p process_noise_std.
/// @param q_n               Length of @p q_var_diag (0 when unused).
DAA_EXPORT int  daa_sim_est_init_from_measurement(Daa_simulator* sim,
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
                                                  int q_n);

/// Time-update (predict) the embedded estimator by one dt.
DAA_EXPORT int  daa_sim_est_predict(Daa_simulator* sim);

/// Measurement-update the embedded estimator.
/// @param z              [3] measurement {az_rad, el_rad, range_ft}.
/// @param meas_noise_std [3] measurement noise std {az_rad, el_rad, range_ft}
///                       for THIS measurement.  Supplied per call so the range
///                       variance can track the measured distance / carry
///                       sensor-reported uncertainty bounds.
/// @param ownship_pos    [3] ownship NED position (ft).
/// @param ownship_att    [3] ownship attitude (rad).
/// @param ownship_cov    [6x6] row-major ownship state covariance.
DAA_EXPORT int  daa_sim_est_update(Daa_simulator* sim,
                                   const double* z,
                                   const double* meas_noise_std,
                                   const double* ownship_pos,
                                   const double* ownship_att,
                                   const double* ownship_cov);

/// Copy out the embedded estimator state / covariance.  Any output
/// pointer may be NULL.
/// @param state6_out [6] state {n,e,d,vn,ve,vd}.
/// @param P36_out    [6x6] row-major covariance.
/// @param accel_var3_out [3] diagonal variances of the acceleration
///        states {var_an, var_ae, var_ad}; 0 for models without an
///        acceleration state (e.g. CV).
DAA_EXPORT int  daa_sim_est_get_state(const Daa_simulator* sim,
                                      double* state6_out,
                                      double* P36_out,
                                      double* accel_var3_out);

/// Propagate the intruder estimate on the uniform look-ahead grid
/// i*dt (i in [0, n)), using the dt configured at daa_sim_create, into
/// the simulator-owned buffers.  @p n must not exceed daa_sim_capacity.
/// Returns 0 on success, negative on error.
DAA_EXPORT int  daa_sim_propagate_batch(Daa_simulator* sim, int n);

/// Number of propagation samples the owned buffers can hold, or -1.
DAA_EXPORT int  daa_sim_capacity(const Daa_simulator* sim);

/// Pointer to the simulator-owned propagated position buffer
/// ([cap x 3] row-major), or NULL.  Overwritten by daa_sim_propagate_batch.
DAA_EXPORT const double* daa_sim_propagation_pos(const Daa_simulator* sim);

/// Pointer to the simulator-owned propagated covariance buffer
/// ([cap x 4] row-major, packed {Pnn, Pne, Pee, Pdd} per sample: the
/// horizontal 2x2 position covariance plus the vertical variance), or
/// NULL.  Overwritten by daa_sim_propagate_batch.
DAA_EXPORT const double* daa_sim_propagation_cov(const Daa_simulator* sim);

/// Fused projection + scoring.  Projects the look-ahead trajectory the
/// ownship would fly under a hypothetical route transform, then scores
/// it against the intruder propagation currently held in the owned
/// buffers (fill them first with daa_sim_propagate_batch), all in one
/// boundary crossing.  The protection cylinder dimensions are taken
/// from the simulator configuration (cyl_h / cyl_d passed to
/// daa_sim_create).
///
/// @param mode        Guidance mode: 0 = track route, 1 = hold velocity,
///                    2 = external track (straight track_p0 -> track_p1).
/// @param shift3      [3] NED shift (mode 0; may be NULL to mean zero).
/// @param speed_scale Segment target-speed scale of the transform (mode 0).
/// @param vel3        [3] NED velocity to hold (mode 1; NULL = zero).
/// @param track_p0    [3] NED segment start (mode 2; NULL = zero).
/// @param track_p1    [3] NED segment end (mode 2; NULL = zero).
/// @param track_speed Constant segment speed in m/s (mode 2).
/// @param traj_out    [n_out x 3] row-major NED positions, or NULL to
///                    use the simulator's internal scratch buffer (the
///                    projection is then discarded, only the score is
///                    returned).
/// @param n_out       Number of samples (>= 1, <= capacity).
/// @param idx_cpa_out Receives the closest-point-of-approach sample
///                    index, or NULL.
/// @return Minimum 1-sigma cylinder distance, or < 0 on bad-arg.
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
                                             int* idx_cpa_out);

#ifdef __cplusplus
}
#endif

#endif // DAA_DLL_H
