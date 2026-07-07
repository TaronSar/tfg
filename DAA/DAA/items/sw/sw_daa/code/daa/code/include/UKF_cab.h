// ---------------------------------------------------------------
// UKF_cab.h — Unscented Kalman Filter with Constant Acceleration in
//             the velocity-aligned (body) frame
// ---------------------------------------------------------------
#ifndef UKF_CAB_H_
#define UKF_CAB_H_

#include <UKF_base.h>

namespace DAA
{

    /// UKF with Constant Acceleration in the velocity-aligned Body frame.
    ///
    /// Unlike UKF_ca, which assumes constant acceleration in NED, this model
    /// assumes constant acceleration in a frame aligned with the horizontal
    /// velocity direction:
    ///   - Tangential: along the horizontal velocity (speed change)
    ///   - Normal:     perpendicular in the horizontal plane (turning)
    ///   - Vertical:   NED down axis (climb/descent rate change)
    ///
    /// State vector (9): [north, east, down, vn, ve, vd, a_tang, a_norm, a_vert]
    /// Measurement  (3): [azimuth, elevation, range]
    class UKF_cab : public UKF_base
    {
    public:
        /// Construct a CAB UKF.  Ownship pose is supplied per-update via
        /// UKF_base::update().
        UKF_cab();
        virtual ~UKF_cab()
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
        /// @param acceleration_var initial acceleration variance (m/s^2)^2, all three axes
        virtual void initialize(const Real64* initial_pos,
                        Real64 dt,
                        Real64 process_noise_std,
                        Real64 position_var,
                        const Real64* initial_vel,
                        Real64 velocity_var,
                        Real64 acceleration_var);

        /// Prediction step: constant body-frame acceleration, sub-stepped
        /// Heun (velocity-midpoint) sigma-point propagation.
        virtual void predict();

        /// Propagate position and covariance on the uniform lookahead
        /// grid i*dt (i in [0, n)).  Covariance is propagated through each
        /// Euler sub-step using the local 9x9 Jacobian.
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
            idx_a_norm_ = 7,  // normal (cross-track) acceleration index
            idx_a_vert_ = 8   // vertical (down) acceleration index
        };
        static const Uint32 state_dim_ = 9;  // state dimension (must be <= State_estimator::MAX_DIM_X)

        /// Convert a body-frame acceleration to NED given current velocity.
        /// @param vel    [3] velocity [vn, ve, vd].
        /// @param a_body [3] body-frame acceleration [tangential, normal, vertical].
        /// @param a_ned  [3] output NED acceleration.
        static void body_to_ned_accel(const Real64* vel, const Real64* a_body, Real64* a_ned);

        /// Integrate position and velocity (and optionally the 9x9 covariance)
        /// forward by tau seconds assuming constant body-frame acceleration.
        /// Uses Heun integration sub-stepped at ~10 Hz.
        /// @param tau    Integration horizon [s].
        /// @param p      [3] in/out position.
        /// @param v      [3] in/out velocity.
        /// @param a_body [3] constant body-frame acceleration.
        /// @param cov9   [81] in/out row-major 9x9 covariance, or 0 to skip.
        static void integrate_segment(Real64 tau, Real64* p, Real64* v, const Real64* a_body, Real64* cov9);

        UKF_cab(const UKF_cab& src);             ///< = delete
        UKF_cab& operator=(const UKF_cab& src);  ///< = delete
    };

}  // namespace DAA

#endif  // UKF_CAB_H_
