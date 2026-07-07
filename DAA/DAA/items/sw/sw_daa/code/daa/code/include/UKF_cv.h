// ---------------------------------------------------------------
// UKF_cv.h — Unscented Kalman Filter with Constant Velocity model
// ---------------------------------------------------------------
#ifndef UKF_CV_H_
#define UKF_CV_H_

#include <UKF_base.h>

namespace DAA
{

    /// UKF with Constant Velocity motion model.
    ///
    /// State vector (6): [north, east, down, vn, ve, vd]
    /// Measurement  (3): [azimuth, elevation, range]
    class UKF_cv : public UKF_base
    {
    public:
        /// Construct a CV UKF.  Ownship pose is supplied per-update via
        /// UKF_base::update().
        UKF_cv();
        virtual ~UKF_cv()
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
        /// @param acceleration_var unused (the CV model has no acceleration
        ///                         state); present so the signature matches
        ///                         the unified UKF_base::initialize.
        virtual void initialize(const Real64* initial_pos,
                        Real64 dt,
                        Real64 process_noise_std,
                        Real64 position_var,
                        const Real64* initial_vel,
                        Real64 velocity_var,
                        Real64 acceleration_var);

        /// Prediction step: constant-velocity sigma-point propagation.
        virtual void predict();

        /// Propagate position and covariance on the uniform lookahead
        /// grid i*dt (i in [0, n)).
        virtual void propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const;

    private:
        enum State_idx
        {
            idx_pn_ = 0, // north position index
            idx_pe_ = 1, // east position index
            idx_pd_ = 2, // down position index
            idx_vn_ = 3, // north velocity index
            idx_ve_ = 4, // east velocity index
            idx_vd_ = 5  // down velocity index
        };
        static const Uint32 state_dim_ = 6; // state dimension (must be <= State_estimator::MAX_DIM_X)

        UKF_cv(const UKF_cv& src);                ///< = delete
        UKF_cv& operator=(const UKF_cv& src);     ///< = delete
    };

}  // namespace DAA

#endif  // UKF_CV_H_
