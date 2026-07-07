// ---------------------------------------------------------------
// UKF_ctra.h — Unscented Kalman Filter with Constant Turn-Rate and
//              tangential Acceleration (horizontal), constant
//              vertical speed.
// ---------------------------------------------------------------
#ifndef UKF_CTRA_H_
#define UKF_CTRA_H_

#include <UKF_base.h>

namespace DAA
{

    /// UKF with Constant Turn-Rate and tangential Acceleration (CTRA).
    ///
    /// Unlike UKF_cab, which carries the horizontal manoeuvre as a normal
    /// (cross-track) acceleration a_norm and derives the turn rate as
    /// omega = a_norm / vh, this model carries the turn rate omega as a
    /// state directly and derives the lateral acceleration as
    /// a_norm = omega * vh.  Removing the division by the horizontal speed
    /// eliminates the low-speed singularity that whips the velocity
    /// direction when vh -> 0 (the source of the CAB velocity spike); a
    /// fixed omega at small vh simply implies a small lateral acceleration.
    ///
    /// The horizontal channel is the textbook constant-turn-rate model
    /// (speed changes at the tangential acceleration a_tang, heading
    /// rotates at omega).  The vertical channel is constant vertical speed
    /// (vd held; no vertical-acceleration state), since tracked aircraft
    /// fly largely level and vertical acceleration is the least observable
    /// state.
    ///
    /// State vector (8): [north, east, down, vn, ve, vd, a_tang, omega]
    ///   - a_tang: tangential (along horizontal velocity) acceleration (m/s^2)
    ///   - omega:  horizontal turn rate (rad/s), positive = clockwise from
    ///             north toward east (right turn in NED)
    /// Measurement  (3): [azimuth, elevation, range]
    class UKF_ctra : public UKF_base
    {
    public:
        /// Construct a CTRA UKF.  Ownship pose is supplied per-update via
        /// UKF_base::update().
        UKF_ctra();
        virtual ~UKF_ctra()
        {
        }

        /// Initialise state, covariance, and noise matrices.
        ///
        /// @param initial_pos      [3] initial intruder position [n, e, d] in feet
        /// @param dt               Time step [s]
        /// @param process_noise_std Process noise standard deviation
        /// @param position_var     initial position variance (m^2), all three axes
        /// @param initial_vel      [3] initial velocity [vn, ve, vd] ft/s
        /// @param velocity_var     initial velocity variance (m/s)^2, all three axes
        /// @param acceleration_var initial tangential-acceleration and turn-rate
        ///                         variance.  Applied to both the a_tang state
        ///                         ((m/s^2)^2) and the omega state ((rad/s)^2);
        ///                         the bootstrap path
        ///                         (initialize_from_measurement) overwrites the
        ///                         turn-rate entry with its dedicated seed.
        virtual void initialize(const Real64* initial_pos,
                        Real64 dt,
                        Real64 process_noise_std,
                        Real64 position_var,
                        const Real64* initial_vel,
                        Real64 velocity_var,
                        Real64 acceleration_var);

        /// Prediction step: constant turn-rate + tangential-acceleration
        /// sigma-point propagation, sub-stepped at ~10 Hz.  The unscented
        /// transform propagates each sigma point through the nonlinear
        /// kinematics; because velocity is stored in Cartesian (vn, ve)
        /// the predicted mean needs no heading-angle unwrapping.
        virtual void predict();

        /// Propagate position and covariance on the uniform lookahead
        /// grid i*dt (i in [0, n)).  Uses the unscented transform: a local
        /// set of sigma points is advanced through the same kinematics and
        /// the position mean / covariance is read from their spread at
        /// each grid step (no analytic Jacobian, hence no 1/vh term).
        virtual void propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const;

    private:
        enum State_idx
        {
            idx_pn_ = 0,      // north position index
            idx_pe_ = 1,      // east position index
            idx_pd_ = 2,      // down position index
            idx_vn_ = 3,      // north velocity index
            idx_ve_ = 4,      // east velocity index
            idx_vd_ = 5,      // down velocity index
            idx_a_tang_ = 6,  // tangential (along-track) acceleration index
            idx_omega_  = 7   // horizontal turn-rate index
        };
        static const Uint32 state_dim_ = 8;  // state dimension (must be <= State_estimator::MAX_DIM_X)

        /// Advance a single CTRA state vector by @p tau seconds in place,
        /// holding a_tang, omega and the vertical speed vd constant.
        /// Sub-stepped at ~10 Hz so the heading-dependent velocity is
        /// re-evaluated through a turn.  No division by the horizontal
        /// speed (atan2 yields a well-defined heading even at vh = 0).
        /// @param y    [state_dim_] in/out CTRA state.
        /// @param tau  Integration horizon [s].
        static void propagate_state(Real64* y, Real64 tau);

        UKF_ctra(const UKF_ctra& src);             ///< = delete
        UKF_ctra& operator=(const UKF_ctra& src);  ///< = delete
    };

}  // namespace DAA

#endif  // UKF_CTRA_H_
