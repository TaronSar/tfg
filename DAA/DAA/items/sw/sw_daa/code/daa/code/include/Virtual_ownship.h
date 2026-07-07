// ---------------------------------------------------------------
// Virtual_ownship.h — Kinematic ownship integrator for candidate
// trajectory generation.
//
// Holds NED position and velocity.  Each step accepts a desired
// NED velocity command, expressed in spherical (course-azimuth,
// flight-path-elevation, speed) form, and limits the per-step
// change of each spherical coordinate independently: the speed
// module by an along-track acceleration cap, and the azimuth and
// elevation by configurable angular-rate caps.  Position is then
// integrated with a trapezoidal (constant-acceleration) rule.
//
// This mirrors the spherical (az/el/d) velocity smoothing used by
// the Vpgnc acceleration limiter (Accelimit::bound_acc_azeld),
// without the wind-difference term.
//
// No allocation, no virtuals, no exceptions: many instances are
// stepped in parallel inside the candidate-generation hot loop.
// ---------------------------------------------------------------
#ifndef VIRTUAL_OWNSHIP_H_
#define VIRTUAL_OWNSHIP_H_

#include <Entypes.h>
#include <Tnarray.h>

namespace DAA
{

    /// Airframe envelope used by :class:`Virtual_ownship`.
    ///
    /// The velocity command is limited in spherical (az/el/d) form:
    ///
    ///   * ``a_max_along``      — speed-module acceleration cap
    ///                            (m/s^2): bounds the per-step change
    ///                            of |v| (the speed magnitude).
    ///   * ``rate_max_azimuth`` — course-angle rate cap (rad/s):
    ///                            bounds the per-step change of the
    ///                            horizontal heading (azimuth).
    ///   * ``rate_max_elevation`` — flight-path-angle rate cap
    ///                            (rad/s): bounds the per-step change
    ///                            of the climb/descent angle
    ///                            (elevation, positive-up).
    ///
    /// Velocity limits are in spherical (speed-module + flight-path
    /// angle) form, so they apply with no coordinate conversion:
    ///
    ///   * ``v_max``  — upper bound on the speed module |v| (m/s).
    ///   * ``v_min``  — lower bound on the speed module |v| (m/s).
    ///                  Stall guard: the speed is floored up to this
    ///                  value once a direction is defined.  A value of
    ///                  0 disables the floor; at rest with no command
    ///                  the airframe stays at rest (no invented speed).
    ///   * ``el_max`` — upper bound on the flight-path elevation
    ///                  (rad, positive-up): the steepest climb angle.
    ///   * ``el_min`` — lower bound on the flight-path elevation
    ///                  (rad, negative-down): the steepest descent
    ///                  angle (a negative value).
    ///
    /// The spherical-rate limits act on the per-step velocity command;
    /// the speed/elevation bounds act on the post-step velocity.  The
    /// speed cap and elevation bounds are always-on: callers pass a
    /// sufficiently large value (speed) or +/- pi/2 (elevation) to
    /// express "effectively no limit".  The default-constructed
    /// envelope sets the accel/rate caps and ``v_max`` to +infinity,
    /// the elevation bounds to +/- infinity, and ``v_min`` to 0.
    struct Flight_envelope
    {
        Real64 a_max_along;        ///< m/s^2 speed-module accel cap
        Real64 rate_max_azimuth;   ///< rad/s  course-angle rate cap
        Real64 rate_max_elevation; ///< rad/s  flight-path-angle rate cap
        Real64 v_max;              ///< m/s  speed-module upper bound
        Real64 v_min;              ///< m/s  speed-module lower bound (stall guard, 0 = off)
        Real64 el_max;             ///< rad  flight-path angle upper bound (climb, +up)
        Real64 el_min;             ///< rad  flight-path angle lower bound (descent, -down)

        /// Default ctor: accel/rate caps + ``v_max`` = +infinity,
        /// elevation bounds = +/- infinity, ``v_min`` = 0.
        Flight_envelope();
    };

    class Virtual_ownship
    {
    public:
        /// Default-constructed state is zero; envelope is unbounded.
        Virtual_ownship();

        // ---- Configuration ---------------------------------------

        /// Replace the active flight envelope (acceleration and
        /// velocity bounds in one shot).  Callers typically build a
        /// default-constructed :struct:`Flight_envelope`, assign the
        /// axes they care about, and pass it in.
        void set_envelope(const Flight_envelope& env);

        // ---- State access ----------------------------------------

        /// Overwrite position [N,E,D] (m).
        void set_position(const Real64* p_ned);

        /// Overwrite velocity [vN,vE,vD] (m/s).
        void set_velocity(const Real64* v_ned);

        /// Copy position out (3 Real64s).
        void get_position(Real64* p_out) const;

        /// Copy velocity out (3 Real64s).
        void get_velocity(Real64* v_out) const;

        // ---- Integration -----------------------------------------

        /// Advance one step under a desired NED velocity command.
        ///
        /// The current velocity and the command are both expressed
        /// in spherical form (course azimuth, flight-path elevation,
        /// speed module).  The speed-module change is clamped to
        /// (a_max_along * dt); the azimuth and elevation changes are
        /// clamped to (rate_max_azimuth * dt) and
        /// (rate_max_elevation * dt) respectively.  The limited
        /// spherical state is converted back to NED and the position
        /// is integrated with the trapezoidal rule using the pre-
        /// and post-clamp velocities.
        ///
        /// If the current speed is below a small epsilon the command
        /// direction is adopted directly (acceleration from rest).
        /// If only the command speed is below epsilon the current
        /// direction is held (deceleration to rest), so no spurious
        /// heading appears when stopping.
        ///
        /// @param v_cmd_ned [3] desired NED velocity (m/s)
        /// @param dt        time step (s), must be > 0
        void step(const Real64* v_cmd_ned, Real64 dt);

    private:
        Base::R64v3 p_;     // NED position (m)
        Base::R64v3 v_;     // NED velocity (m/s) cache of (az_,el_,d_)
        Real64 az_;         // course azimuth (rad)
        Real64 el_;         // flight-path elevation (rad, +up)
        Real64 d_;          // speed module (m/s)
        Flight_envelope env_;

        Virtual_ownship(const Virtual_ownship& src);             ///< = delete.
        Virtual_ownship& operator=(const Virtual_ownship& src);  ///< = delete.
    };

}  // namespace DAA

#endif  // VIRTUAL_OWNSHIP_H_
