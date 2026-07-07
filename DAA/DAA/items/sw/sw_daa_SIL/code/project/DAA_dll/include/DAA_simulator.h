// ---------------------------------------------------------------
// DAA_simulator.h — Stateful driver that flies a Virtual_ownship
// along a Route_tracker route, one step at a time, and can project
// the look-ahead trajectory under a hypothetical route transform.
//
// Composition:
//   * Route_tracker   — the route still to be flown (waypoints +
//                       per-segment durations).
//   * Virtual_ownship — the current kinematic flight state.
//   * Route_transform  current_route_xf — affine modifier applied to
//                       the route on the fly (shift + dt scale),
//                       initially the identity.
//
// step() advances the real flight by cfg.dt (sub-stepped at
// cfg.sim_dt_max) under current_route_xf and pops surpassed
// waypoints from the tracker.  simulate() projects the look-ahead
// trajectory under a *different* transform without mutating the
// simulator.
//
// No virtuals, no exceptions, no dynamic allocation of its own (the
// internal Route_tracker owns its single malloc).
// ---------------------------------------------------------------
#ifndef DAA_SIMULATOR_H_
#define DAA_SIMULATOR_H_

#include <Entypes.h>
#include <Route_tracker.h>
#include <Route_transform.h>
#include <Virtual_ownship.h>
#include <UKF_base.h>
#include <UKF_cv.h>
#include <UKF_ca.h>
#include <UKF_cab.h>
#include <UKF_ctra.h>

namespace DAA
{

    /// Motion model of the embedded intruder estimator.  Selected at
    /// construction time and used to pick which concrete UKF the
    /// simulator drives through its UKF_base pointer.  Ordered so the
    /// constant-velocity model is the default (first) choice.
    enum Ukf_model
    {
        UKF_MODEL_CV   = 0,  ///< Constant-velocity (6-state).
        UKF_MODEL_CA   = 1,  ///< Constant-acceleration, NED frame (9-state).
        UKF_MODEL_CAB  = 2,  ///< Constant-acceleration, body frame (9-state).
        UKF_MODEL_CTRA = 3   ///< Constant turn-rate + tangential accel,
                             ///< constant vertical speed (8-state).
    };

    /// Configuration bag for :class:`DAA_simulator`.  Aggregate: the
    /// caller default-constructs it (env gets the unbounded
    /// Flight_envelope) and fills the fields it cares about.
    struct DAA_simulator_cfg
    {
        Real64 dt;              ///< Real-flight step duration (s) for step().
        Uint32 lookahead;       ///< Number of look-ahead samples for simulate().
        Real64 sim_dt_max;      ///< Maximum integration sub-step (s).
        Real64 k_xt;            ///< Cross-track line-attraction gain (1/m).
        Real64 p0_ned[3];       ///< Initial ownship NED position (ft).
        Real64 v0_ned[3];       ///< Initial ownship NED velocity (ft/s).
        Uint32 route_capacity;  ///< Waypoint capacity of the internal tracker.
        Flight_envelope env;    ///< Airframe flight envelope.
        Real64 ukf_alpha;       ///< UKF sigma-point spread parameter.
        Real64 ukf_beta;        ///< UKF distribution prior parameter.
        Real64 ukf_kappa;       ///< UKF secondary scaling parameter.
        Real64 cyl_h;           ///< Protection cylinder half-height (ft).
        Real64 cyl_d;           ///< Protection cylinder diameter (ft).
        Ukf_model ukf_model;    ///< Embedded intruder estimator motion model.
    };

    class DAA_simulator
    {
    public:
        /// Build a simulator: allocate the route tracker with
        /// cfg.route_capacity slots, seed the ownship with cfg.p0_ned
        /// / cfg.v0_ned / cfg.env, and set current_route_xf to the
        /// identity.
        explicit DAA_simulator(const DAA_simulator_cfg& cfg);

        /// Destructor.
        ~DAA_simulator();

        // ---- Route access -----------------------------------------

        /// Append waypoints to the route to fly.  Forwards to
        /// Route_tracker::push_batch on the internal tracker.
        ///
        /// @param pdt_n4 [n x 4] row-major waypoints, each row
        ///               [N, E, D, dt] (NED ft + per-segment duration s).
        /// @param n      Number of waypoints to push.
        /// @return Number of waypoints actually pushed (< n if the
        ///         tracker's capacity is reached).
        Uint32 push_route(const Real64* pdt_n4, Uint32 n);

        // ---- Current route transform ------------------------------

        /// Replace the active route transform (shift + dt scale).
        void set_route_xf(const Route_transform& xf);

        /// The active route transform (identity until set).
        const Route_transform& route_xf() const;

        // ---- Ownship state ----------------------------------------

        /// Copy out the current ownship position (3 Real64s, NED ft).
        void get_position(Real64* p_out) const;

        /// Copy out the current ownship velocity (3 Real64s, NED ft/s).
        void get_velocity(Real64* v_out) const;

        // ---- Stepping ---------------------------------------------

        /// Advance the real flight by cfg.dt under current_route_xf
        /// (sub-stepped at cfg.sim_dt_max) and pop every waypoint the
        /// ownship has now surpassed from the tracker.
        ///
        /// The per-step quantities the caller needs each cycle are
        /// reported through optional output pointers (any may be NULL
        /// to skip):
        ///
        /// @param p_out        [3] new ownship NED position (ft).
        /// @param v_out        [3] new ownship NED velocity (ft/s).
        /// @param track_pt_out [3] foot of perpendicular of the new
        ///                     position onto the active route segment
        ///                     (the "track point", NED ft).  Equals the
        ///                     current position when the route has a
        ///                     single waypoint left or is exhausted.
        void step(Real64* p_out = 0,
                  Real64* v_out = 0,
                  Real64* track_pt_out = 0);

        // ---- Look-ahead projection --------------------------------

        /// Project the look-ahead trajectory the ownship would fly
        /// from its current state under @p route_xf, without modifying
        /// this simulator or its tracker.
        ///
        /// Samples are spaced cfg.dt apart in time (each sample
        /// advances the projection by one cfg.dt, sub-stepped at
        /// cfg.sim_dt_max).
        ///
        /// @param route_xf  Hypothetical affine route transform.
        /// @param traj_out  [n_out x 3] row-major NED positions (ft).
        ///                  traj_out[0] is the current position.
        /// @param n_out     Number of samples to write (>= 1).
        void simulate(const Route_transform& route_xf,
                      Real64* traj_out,
                      Uint32 n_out) const;

        // ---- Embedded intruder estimator (UKF) --------------------

        /// Initialise the embedded UKF from a single first measurement.
        /// The intruder NED position and an anisotropic position
        /// covariance are derived from the measurement geometry inside
        /// the estimator; velocity / acceleration are seeded to zero
        /// with the supplied variances and refined by the subsequent
        /// est_predict() / est_update() stream.  Mirrors
        /// UKF_base::initialize_from_measurement.
        ///
        /// @param z                 [3] measurement {az_rad, el_rad, range_ft}.
        /// @param ownship_pos       [3] ownship NED position (ft).
        /// @param ownship_att       [3] ownship attitude (rad).
        /// @param ownship_cov       [6x6] row-major ownship state covariance.
        /// @param dt                Filter time step (s).
        /// @param process_noise_std Process noise standard deviation.
        /// @param meas_noise_std    [3] measurement noise std {az, el, range}.
        /// @param velocity_var      Initial horizontal velocity variance ((ft/s)^2).
        /// @param acceleration_var  Initial horizontal acceleration variance
        ///                          ((ft/s^2)^2); ignored by models without
        ///                          an acceleration state.
        /// @param velocity_var_vertical     Initial vertical (down) velocity
        ///                          variance ((ft/s)^2); tighter than the
        ///                          horizontal seed as aircraft fly largely level.
        /// @param acceleration_var_vertical Initial vertical (down) acceleration
        ///                          variance ((ft/s^2)^2); ignored by models
        ///                          without an acceleration state.
        /// @param q_var_diag        Optional [q_n] per-state process-noise
        ///                          variance diagonal.  When non-NULL and
        ///                          @p q_n equals the model state dimension it
        ///                          overrides Q's diagonal so each manoeuvre
        ///                          channel is tuned independently (needed for
        ///                          CTRA's mixed acceleration / turn-rate
        ///                          states).  NULL keeps the model's own Q.
        /// @param q_n               Length of @p q_var_diag (0 when unused).
        void est_initialize_from_measurement(const Real64* z,
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
                                             const Real64* q_var_diag = 0,
                                             Uint32 q_n = 0);

        /// Time-update (predict) the embedded estimator by one dt.
        void est_predict();

        /// Measurement-update the embedded estimator.
        ///
        /// @param z              [3] measurement {az_rad, el_rad, range_ft}.
        /// @param meas_noise_std [3] measurement noise std {az_rad, el_rad,
        ///                       range_ft} for THIS measurement.  Supplied per
        ///                       call so the range variance can track the
        ///                       measured distance / carry sensor-reported
        ///                       uncertainty bounds.
        /// @param ownship_pos    [3] ownship NED position (ft).
        /// @param ownship_att    [3] ownship attitude (rad).
        /// @param ownship_cov    [6x6] row-major ownship state covariance.
        void est_update(const Real64* z,
                        const Real64* meas_noise_std,
                        const Real64* ownship_pos,
                        const Real64* ownship_att,
                        const Real64* ownship_cov);

        /// Copy out the estimator state and covariance.
        ///
        /// @param state6_out [6] state {n,e,d,vn,ve,vd} or NULL.
        /// @param cov36_out  [6x6] row-major covariance or NULL.
        /// @param accel_var3_out [3] diagonal variances of the
        ///        acceleration states {var_an, var_ae, var_ad} or NULL.
        ///        Filled with 0 for models without an acceleration state
        ///        (e.g. the CV model).
        void est_get_state(Real64* state6_out, Real64* cov36_out,
                           Real64* accel_var3_out = 0) const;

        /// Propagate the intruder estimate forward under the
        /// configured motion model on the uniform look-ahead grid
        /// i*dt (i in [0, n)), where dt is the configured step.
        ///
        /// @param n       Number of samples.
        /// @param pos_out [n x 3] row-major predicted positions (ft).
        /// @param cov_out [n x 4] row-major packed position covariance
        ///                {Pnn, Pne, Pee, Pdd} per sample.
        void est_propagate_batch(int n,
                                 Real64* pos_out,
                                 Real64* cov_out) const;

        /// Fused projection + scoring: project the ownship look-ahead
        /// trajectory under @p route_xf into @p traj_out, then score it
        /// against the supplied propagated intruder track and return the
        /// minimum 1-sigma cylinder distance.  The protection cylinder
        /// dimensions are taken from the simulator configuration
        /// (cfg.cyl_h / cfg.cyl_d).
        ///
        /// @param route_xf    Hypothetical affine route transform.
        /// @param traj_out    [n_out x 3] row-major projected positions.
        /// @param n_out       Number of samples (>= 1).
        /// @param int_pos     [n_out x 3] propagated intruder positions.
        /// @param int_cov     [n_out x 4] propagated intruder packed
        ///                    position covariance {Pnn, Pne, Pee, Pdd}.
        /// @param idx_cpa_out Index of the closest-point-of-approach
        ///                    sample, or NULL.
        /// @return Minimum 1-sigma cylinder distance over the horizon.
        Real64 simulate_and_score(const Route_transform& route_xf,
                                  Real64* traj_out,
                                  Uint32 n_out,
                                  const Real64* int_pos,
                                  const Real64* int_cov,
                                  int* idx_cpa_out) const;

    private:
        DAA_simulator_cfg cfg_;
        Route_tracker     route_;
        Virtual_ownship   own_;
        Route_transform   current_route_xf_;

        // One concrete estimator per supported motion model is held
        // in-object (no dynamic allocation); estimator_ points at the
        // one selected by cfg_.ukf_model so the rest of the class drives
        // it polymorphically through the UKF_base interface.
        UKF_cv            estimator_cv_;
        UKF_ca            estimator_ca_;
        UKF_cab           estimator_cab_;
        UKF_ctra          estimator_ctra_;
        UKF_base*         estimator_;

        // Non-copyable.
        DAA_simulator(const DAA_simulator&);
        DAA_simulator& operator=(const DAA_simulator&);
    };

}  // namespace DAA

#endif  // DAA_SIMULATOR_H_
