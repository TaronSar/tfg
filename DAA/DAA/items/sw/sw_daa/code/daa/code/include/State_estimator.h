// ---------------------------------------------------------------
// State_estimator.h — Abstract base class for state estimators
// ---------------------------------------------------------------
#ifndef STATE_ESTIMATOR_H_
#define STATE_ESTIMATOR_H_

#include <R64matrixn.h>
#include <R64vectorn.h>

namespace DAA
{

    /// Abstract base class for state estimators used in intruder tracking.
    ///
    /// All estimators track at minimum position [north, east, down] and
    /// velocity [vn, ve, vd] of the intruder in NED frame.  Subclasses
    /// may track additional states (e.g. acceleration).
    ///
    /// Maximum array dimensions are fixed at compile time so that all
    /// storage is stack-allocated.  Actual dimensions are set at
    /// construction time and must not exceed the maximums.
    ///
    /// Uses Real64 precision throughout because the DLL/SIL interface
    /// operates on Real64s and the UKF needs the extra precision.
    class State_estimator
    {
    public:
        static const Uint32 MAX_DIM_X = 12;  // Maximum state dimension
        static const Uint32 MAX_DIM_Z = 6;   // Maximum measurement dimension

        /// Column layout of the per-sample position-covariance output
        /// shared by propagate_batch() and min_1sigma_cylinder_distance().
        ///
        /// Only the terms the protection-cylinder test consumes are
        /// carried, so the layout is the same for every motion model
        /// regardless of internal state dimension: the horizontal 2x2
        /// position covariance (symmetric) and the vertical variance.
        /// This is exactly the cylinder's own decomposition (a horizontal
        /// disk plus a vertical extent).  Row stride is COV_STRIDE.
        enum Pos_cov_idx
        {
            COV_PNN = 0,     ///< horizontal north-north variance P[0,0]
            COV_PNE = 1,     ///< horizontal north-east  cov      P[0,1] (= P[1,0])
            COV_PEE = 2,     ///< horizontal east-east  variance  P[1,1]
            COV_PDD = 3,     ///< vertical down variance          P[2,2]
            COV_STRIDE = 4   ///< values stored per lookahead sample
        };

        /// @param dim_x State dimension (must be <= MAX_DIM_X).
        /// @param dim_z Measurement dimension (must be <= MAX_DIM_Z).
        State_estimator(Uint32 dim_x, Uint32 dim_z);

        virtual ~State_estimator()
        {
        }

        /// State dimension.
        Uint32 dim_x() const
        {
            return dim_x_;
        }
        /// Measurement dimension.
        Uint32 dim_z() const
        {
            return dim_z_;
        }

        /// Prediction (time update) step.
        virtual void predict() = 0;

        /// Measurement update step.
        /// @param z              Measurement vector [azimuth, elevation, range].
        /// @param meas_noise_std [3] measurement noise std {az_rad, el_rad,
        ///                       range_m} for THIS measurement.  Supplied per
        ///                       call (rather than held as a fixed member) so
        ///                       the range variance can track the measured
        ///                       distance (e.g. a fraction of range) and so a
        ///                       sensor can inject per-frame uncertainty bounds.
        /// @param ownship_pos    Ownship position [n, e, d] (m).
        /// @param ownship_att    Ownship attitude [r, p, y] (rad).
        /// @param ownship_cov    6x6 ownship covariance.
        virtual void update(const Maverick::R64vector& z,
                            const Real64* meas_noise_std,
                            const Maverick::R64vector& ownship_pos,
                            const Maverick::R64vector& ownship_att,
                            const Maverick::R64matrix& ownship_cov) = 0;

        /// Read-only access to state vector.
        const Maverick::R64vector& state() const
        {
            return x_;
        }
        /// Mutable access to state vector.
        Maverick::R64vector& state()
        {
            return x_;
        }

        /// Read-only access to covariance matrix (dim_x x dim_x column-major).
        const Maverick::R64matrix& covariance() const
        {
            return P_;
        }
        /// Mutable access to covariance matrix (dim_x x dim_x column-major).
        Maverick::R64matrix& covariance()
        {
            return P_;
        }

        /// Current time step [s].
        Real64 dt() const
        {
            return dt_;
        }

        /// Propagate position and covariance on the uniform lookahead
        /// grid i*dt (i in [0, n)).
        /// @param dt      lookahead step [s]
        /// @param n       Number of lookahead samples
        /// @param pos_out [N x 3] row-major position output [ft]
        /// @param cov_out [N x COV_STRIDE] row-major position covariance
        ///                packed per Pos_cov_idx (horizontal 2x2 + vertical
        ///                variance).  Required.
        virtual void propagate_batch(Real64 dt, Uint32 n, Real64* pos_out, Real64* cov_out) const = 0;

        /// Minimum 1-sigma cylinder distance along a user-supplied ownship
        /// trajectory.
        ///
        /// Compute the minimum 1-sigma cylinder distance over a supplied
        /// ownship trajectory and a pre-computed intruder propagation.
        ///
        /// The caller is responsible for propagating the intruder state
        /// (typically with propagate_batch) into @p int_pos and @p int_cov.
        /// Keeping the propagation outside this method allows the caller
        /// to reuse it when evaluating multiple ownship trajectories.
        ///
        /// @param own_traj    [N x 3] ownship NED positions at each sample
        ///                    (m), row-major.
        /// @param int_pos     [N x 3] row-major intruder propagated
        ///                    positions (m).
        /// @param int_cov     [N x COV_STRIDE] row-major intruder
        ///                    propagated position covariance, packed per
        ///                    Pos_cov_idx (m^2).
        /// @param N           Number of trajectory samples.
        /// @param cyl_h       Protection cylinder height (m).
        /// @param cyl_d       Protection cylinder diameter (m).
        /// @param idx_cpa_out Optional output: sample index of the
        ///                    reported distance.  When a conflict is
        ///                    predicted (cylinder distance < 1 at any
        ///                    sample) this is the index of the FIRST
        ///                    such sample and the scan stops there;
        ///                    when no conflict is predicted it is the
        ///                    sample that minimises the distance (CPA).
        ///                    Range [0, N).  May be NULL.
        /// @return First sub-unity 1-sigma cylinder distance if a
        ///         conflict is predicted, otherwise the minimum over
        ///         all samples (dimensionless).
        Real64 min_1sigma_cylinder_distance(const Real64* own_traj,
                                            const Real64* int_pos,
                                            const Real64* int_cov,
                                            Uint32 N,
                                            Real64 cyl_h,
                                            Real64 cyl_d,
                                            int* idx_cpa_out) const;

        /// Override the process-noise covariance Q with a diagonal built
        /// from the supplied per-state variances.
        ///
        /// @p q_var_diag must hold dim_x() entries — the process-noise
        /// variance for each state, in state order.  Off-diagonal terms
        /// are zeroed.  This lets a caller tune each channel
        /// independently instead of through one lumped scalar, which
        /// matters when the states carry different physical quantities
        /// (e.g. the CTRA model's tangential acceleration in (m/s^2)^2
        /// versus its turn rate in (rad/s)^2): a single value sized for
        /// one channel is wildly wrong for the other.  Call after
        /// initialize(); intended for models with a diagonal Q.
        ///
        /// @param q_var_diag dim_x() process-noise variances.
        void set_process_noise_diag(const Real64* q_var_diag);

    protected:
        Uint32 dim_x_;                       ///< Actual state dimension.
        Uint32 dim_z_;                       ///< Actual measurement dimension.
        Maverick::R64vectorn<MAX_DIM_X> x_;  ///< State vector.
        Maverick::R64matrixn<MAX_DIM_X> P_;  ///< State covariance (column-major).
        Maverick::R64matrixn<MAX_DIM_X> Q_;  ///< Process noise covariance (column-major).
        Real64 dt_;                          ///< Time step [s].
    };

}  // namespace DAA

#endif  // STATE_ESTIMATOR_H_
