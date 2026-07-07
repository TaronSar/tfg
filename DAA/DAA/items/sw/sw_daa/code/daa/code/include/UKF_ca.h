// ---------------------------------------------------------------
// UKF_ca.h — Unscented Kalman Filter with Constant Acceleration model
// ---------------------------------------------------------------
#ifndef UKF_CA_H_
#define UKF_CA_H_

#include <UKF_base.h>

namespace DAA
{

    /// UKF with Constant Acceleration motion model.
    ///
    /// State vector (9): [north, east, down, vn, ve, vd, an, ae, ad]
    /// Measurement  (3): [azimuth, elevation, range]
    class UKF_ca : public UKF_base
    {
    public:
        /// Construct a CA UKF.  Ownship pose is supplied per-update via
        /// UKF_base::update().
        UKF_ca();
        virtual ~UKF_ca()
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

        /// Prediction step: constant-acceleration sigma-point propagation.
        virtual void predict();

        /// Propagate position and covariance on the uniform lookahead
        /// grid i*dt (i in [0, n)).
        virtual void propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const;

    private:
        enum State_idx
        {
            idx_pn_ = 0,  // north position index
            idx_pe_ = 1,  // east position index
            idx_pd_ = 2,  // down position index
            idx_vn_ = 3,  // north velocity index
            idx_ve_ = 4,  // east velocity index
            idx_vd_ = 5,  // down velocity index
            idx_an_ = 6,  // north acceleration index
            idx_ae_ = 7,  // east acceleration index
            idx_ad_ = 8   // down acceleration index
        };
        static const Uint32 state_dim_ = 9;  // state dimension (must be <= State_estimator::MAX_DIM_X)

        UKF_ca(const UKF_ca& src);             ///< = delete
        UKF_ca& operator=(const UKF_ca& src);  ///< = delete
    };

}  // namespace DAA

#endif  // UKF_CA_H_
