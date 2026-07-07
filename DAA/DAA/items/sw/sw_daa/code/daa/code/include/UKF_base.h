// ---------------------------------------------------------------
// UKF_base.h — Base Unscented Kalman Filter (UKF machinery)
// ---------------------------------------------------------------
#ifndef UKF_BASE_H_
#define UKF_BASE_H_

#include <State_estimator.h>

#include <cmath>
#include <cstring>

namespace DAA
{

    /// Base UKF that implements sigma-point generation, measurement model,
    /// ownship-induced noise, and the common measurement-update step.
    ///
    /// Subclasses implement: initialize, predict, get_state_dict,
    /// propagate_batch.
    class UKF_base : public State_estimator
    {
    public:
        static const Uint32 MAX_N_SIGMA = 2 * State_estimator::MAX_DIM_X + 1; // Maximum number of sigma points

        /// @param dim_x        State dimension (must be <= MAX_DIM_X).
        /// @param dim_z        Measurement dimension (must be <= MAX_DIM_Z).
        UKF_base(Uint32 dim_x, Uint32 dim_z);
        virtual ~UKF_base()
        {
        }

        /// Set UKF tuning parameters.  Must be called before initialize.
        void set_ukf_params(Real64 alpha, Real64 beta, Real64 kappa);

        /// Initialise state, covariance, and noise matrices.
        ///
        /// Unified across all motion models so a freshly-constructed
        /// estimator can be initialised through a UKF_base pointer
        /// (e.g. by a factory) regardless of its internal state layout.
        /// Models without an acceleration state ignore @p acceleration_var.
        ///
        /// @param initial_pos       [3] initial intruder position [n, e, d] (m).
        /// @param dt                Time step [s].
        /// @param process_noise_std Process noise standard deviation.
        /// @param position_var      Initial position variance (m^2), all three axes.
        /// @param initial_vel       [3] initial velocity [vn, ve, vd] (m/s).
        /// @param velocity_var      Initial velocity variance ((m/s)^2), all three axes.
        /// @param acceleration_var  Initial acceleration variance ((m/s^2)^2), all
        ///                          three axes.  Ignored by models without an
        ///                          acceleration state.
        virtual void initialize(const Real64* initial_pos,
                                Real64 dt,
                                Real64 process_noise_std,
                                Real64 position_var,
                                const Real64* initial_vel,
                                Real64 velocity_var,
                                Real64 acceleration_var) = 0;

        /// Initialise the filter from a single first measurement.
        ///
        /// Bootstraps the track on first sighting without any externally
        /// supplied velocity seed.  The measurement is back-projected to
        /// an NED position; the initial position covariance is built
        /// anisotropically from the measurement geometry (the large
        /// range error falls along the line of sight, the angular errors
        /// across it) plus the ownship position covariance.  Velocity
        /// and acceleration are seeded to zero with the supplied
        /// variances, so the subsequent predict()/update() stream — fed
        /// every in-FOV frame — estimates them with correct per-sample
        /// weighting.  This replaces the previous finite-difference
        /// velocity seed that discarded all but two warm-up samples and
        /// drove the acceleration states of the CA/CAB models unstable.
        ///
        /// @param z                 [3] measurement {az_rad, el_rad, range_m}.
        /// @param ownship_pos       [3] ownship NED position (m).
        /// @param ownship_att       [3] ownship attitude {roll, pitch, yaw} (rad).
        /// @param ownship_cov       [6x6] row-major ownship state covariance.
        /// @param dt                Time step [s].
        /// @param process_noise_std Process noise standard deviation.
        /// @param meas_noise_std    [3] measurement noise std {az_rad, el_rad, range_m}.
        /// @param velocity_var      Initial horizontal velocity variance
        ///                          ((m/s)^2), applied to the north / east
        ///                          velocity states.
        /// @param acceleration_var  Initial horizontal acceleration variance
        ///                          ((m/s^2)^2), applied to the horizontal
        ///                          acceleration states.  Ignored by models
        ///                          without an acceleration state.
        /// @param velocity_var_vertical
        ///                          Initial vertical (down) velocity variance
        ///                          ((m/s)^2).  Aircraft trajectories are
        ///                          largely level, so the vertical rate is far
        ///                          more tightly bounded than the horizontal
        ///                          speed; seed it separately to keep the
        ///                          predicted altitude envelope from fanning
        ///                          out over the lookahead horizon.
        /// @param acceleration_var_vertical
        ///                          Initial vertical (down) acceleration
        ///                          variance ((m/s^2)^2).  Ignored by models
        ///                          without an acceleration state.
        /// @param q_var_diag        Optional per-state process-noise variance
        ///                          diagonal (length @p q_n).  When non-NULL
        ///                          and @p q_n equals the state dimension it
        ///                          overrides the diagonal of the process-
        ///                          noise covariance Q that the per-model
        ///                          initialise built from
        ///                          @p process_noise_std.  This lets a model
        ///                          whose states carry different physical
        ///                          quantities (e.g. CTRA's tangential
        ///                          acceleration vs turn rate) tune each
        ///                          channel independently instead of through
        ///                          one lumped scalar.  NULL keeps the
        ///                          model's own Q (the structured jerk Q of
        ///                          CA / CAB relies on this).
        /// @param q_n               Length of @p q_var_diag (0 when unused).
        void initialize_from_measurement(const Real64* z,
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

        /// Common UKF measurement-update step.
        ///
        /// The ownship pose and the measurement noise are both supplied at
        /// call time (not held by the filter): the pose is only needed during
        /// the update, and the noise is per-measurement so the range variance
        /// can track the measured distance / carry sensor-reported bounds.
        ///
        /// @param z              Measurement [az, el, range].
        /// @param meas_noise_std [3] measurement noise std {az_rad, el_rad,
        ///                       range_m} for THIS measurement.
        /// @param ownship_pos    Ownship position [n, e, d] (m).
        /// @param ownship_att    Ownship attitude [r, p, y] (rad).
        /// @param ownship_cov    6x6 ownship covariance.
        virtual void update(const Maverick::R64vector& z,
                            const Real64* meas_noise_std,
                            const Maverick::R64vector& ownship_pos,
                            const Maverick::R64vector& ownship_att,
                            const Maverick::R64matrix& ownship_cov);

    protected:
        Uint32 n_sigma_;  ///< 2 * dim_x + 1.

        // UKF tuning
        Real64 alpha_;
        Real64 beta_;
        Real64 kappa_;
        Real64 lambda_;

        // Sigma-point weights
        Real64 wm_[MAX_N_SIGMA];  ///< Mean weights.
        Real64 wc_[MAX_N_SIGMA];  ///< Covariance weights.

        // Sigma points storage
        Real64 sigma_pts_[MAX_N_SIGMA * MAX_DIM_X];  ///< (n_sigma x dim_x) row-major.
        Real64 sigma_z_[MAX_N_SIGMA * MAX_DIM_Z];    ///< (n_sigma x dim_z) row-major.

        /// Recompute weights from alpha_, beta_, kappa_.
        void compute_weights();

        /// Generate sigma points around x with covariance P.
        /// Output written to out (n_sig x dim row-major).
        /// @param lambda_val  Scaling parameter (use lambda_ by default).
        /// @return true on success, false if Cholesky fails.
        bool generate_sigma_points(const Real64* x,
                                   const Maverick::R64matrix& P,
                                   Uint32 dim,
                                   Real64* out,
                                   Real64 lambda_val) const;

        /// Generate sigma points using the estimator's state and covariance.
        /// @return true on success, false if Cholesky fails.
        bool generate_sigma_points_state();

        /// Measurement function: intruder state -> [azimuth, elevation, range].
        static void measurement_function(const Real64* state,
                                         const Real64* ownship_pos,
                                         const Real64* ownship_att,
                                         Real64* z_out);

        /// Compute ownship-induced measurement noise via mini Unscented Transform.
        /// @return true on success, false if Cholesky fails.
        bool compute_ownship_induced_noise(const Maverick::R64vector& intruder_state,
                                           const Maverick::R64vector& ownship_pos,
                                           const Maverick::R64vector& ownship_att,
                                           const Maverick::R64matrix& ownship_cov,
                                           Maverick::R64matrix& R_induced) const;

        /// Wrap angle to (-pi, pi].
        static Real64 wrap_angle(Real64 a);

    private:
        UKF_base(const UKF_base& src);            ///< = delete
        UKF_base& operator=(const UKF_base& src); ///< = delete
    };

    // =====================================================================
    // Short inline implementations
    // =====================================================================

    inline void UKF_base::set_ukf_params(Real64 alpha, Real64 beta, Real64 kappa)
    {
        alpha_ = alpha;
        beta_ = beta;
        kappa_ = kappa;
        compute_weights();
    }

    inline void UKF_base::compute_weights()
    {
        lambda_ = alpha_ * alpha_ * (dim_x_ + kappa_) - dim_x_;

        wm_[0] = lambda_ / (dim_x_ + lambda_);
        wc_[0] = lambda_ / (dim_x_ + lambda_) + (1.0 - alpha_ * alpha_ + beta_);

        const Real64 w = 1.0 / (2.0 * (dim_x_ + lambda_));
        for (Uint32 i = 1; i < n_sigma_; ++i)
        {
            wm_[i] = w;
            wc_[i] = w;
        }
    }

    inline Real64 UKF_base::wrap_angle(Real64 a)
    {
        const Real64 pi = 3.14159265358979323846;
        const Real64 two_pi = 2.0 * pi;
        a = fmod(a + pi, two_pi);
        if (a < 0.0)
        {
            a += two_pi;
        }
        return a - pi;
    }

    inline bool UKF_base::generate_sigma_points_state()
    {
        return generate_sigma_points(x_.first(), P_, dim_x_, sigma_pts_, lambda_);
    }

}  // namespace DAA

#endif  // UKF_BASE_H_
