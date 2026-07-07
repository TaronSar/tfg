// ---------------------------------------------------------------
// Virtual_ownship.cpp — implementation of the kinematic ownship
// integrator declared in Virtual_ownship.h.
// ---------------------------------------------------------------
#include <Kr64.h>
#include <Rfun.h>
#include <Rmath.h>
#include <Virtual_ownship.h>

namespace DAA
{

    // Fast wrap of an angle already known to lie within [-2*pi, 2*pi]
    // (a sum or difference of atan2 results) to the range (-pi, pi].
    // A single signed correction is exact for that bounded input and
    // avoids the round()+two multiplies of the general Rfun::wrap2pi,
    // which dominated the per-step cost.
    static Real64 wrap_pi_bounded(Real64 ang)
    {
        Real64 wrapped = ang;
        if (ang > Kr64::PI)
        {
            wrapped = ang - Kr64::PI2;
        }
        else if (ang < -Kr64::PI)
        {
            wrapped = ang + Kr64::PI2;
        }
        return wrapped;
    }

    Flight_envelope::Flight_envelope() :
            a_max_along(INFINITY),
            rate_max_azimuth(INFINITY),
            rate_max_elevation(INFINITY),
            v_max(INFINITY),
            v_min(0.0),
            el_max(INFINITY),
            el_min(-INFINITY)
    {
    }

    Virtual_ownship::Virtual_ownship() :
            p_(),
            v_(),
            az_(0.0),
            el_(0.0),
            d_(0.0),
            env_()
    {
        p_.zeros();
        v_.zeros();
    }

    void Virtual_ownship::set_envelope(const Flight_envelope& env)
    {
        env_ = env;
    }

    void Virtual_ownship::set_position(const Real64* p_ned)
    {
        p_.copy_all(p_ned);
    }

    void Virtual_ownship::set_velocity(const Real64* v_ned)
    {
        v_.copy_all(v_ned);

        // Cache the spherical form so step() needs no NED->spherical
        // conversion of the current velocity each call.
        const Real64 vh = Rmath::sqrtr(v_ned[0] * v_ned[0]
                                       + v_ned[1] * v_ned[1]);
        d_  = Rmath::sqrtr(vh * vh + v_ned[2] * v_ned[2]);
        az_ = Rmath::atan2r(v_ned[1], v_ned[0]);
        el_ = Rmath::atan2r(-v_ned[2], vh);
    }

    void Virtual_ownship::get_position(Real64* p_out) const
    {
        p_out[0] = p_[0];
        p_out[1] = p_[1];
        p_out[2] = p_[2];
    }

    void Virtual_ownship::get_velocity(Real64* v_out) const
    {
        v_out[0] = v_[0];
        v_out[1] = v_[1];
        v_out[2] = v_[2];
    }

    void Virtual_ownship::step(const Real64* v_cmd_ned, Real64 dt)
    {
        static const Real64 epsilon = 1.0E-6;  // m/s, speed floor below which a direction is undefined

        // Current velocity already stored in spherical form: course
        // azimuth (rad), flight-path elevation (rad, positive-up),
        // speed module (m/s).  No NED->spherical conversion needed.
        const Real64 d0  = d_;
        const Real64 az0 = az_;
        const Real64 el0 = el_;

        // Commanded velocity in spherical form (the only per-step
        // NED->spherical conversion; the command arrives in NED).
        const Real64 chx = v_cmd_ned[0] * v_cmd_ned[0]
                         + v_cmd_ned[1] * v_cmd_ned[1];
        const Real64 vhc = Rmath::sqrtr(chx);
        const Real64 dc  = Rmath::sqrtr(chx + v_cmd_ned[2] * v_cmd_ned[2]);
        const Real64 azc = Rmath::atan2r(v_cmd_ned[1], v_cmd_ned[0]);
        const Real64 elc = Rmath::atan2r(-v_cmd_ned[2], vhc);

        // A speed below epsilon leaves the corresponding direction
        // undefined; these flags gate the heading logic below.
        const bool own_moving = (d0 > epsilon);
        const bool cmd_moving = (dc > epsilon);

        // Limit the speed-module change by the along-track accel cap,
        // then bound the result to the speed envelope.  The stall
        // floor (v_min) only acts once a direction is defined: at rest
        // with no command the airframe stays at rest rather than have
        // a speed invented for it in an arbitrary heading.
        const Real64 d_inc_max = env_.a_max_along * dt;
        const Real64 d_inc = Rfun::clamp<Real64>(dc - d0,
                                                 -d_inc_max, d_inc_max);
        const bool at_rest = (!own_moving) && (!cmd_moving);
        const Real64 d_floor = at_rest ? 0.0 : env_.v_min;
        const Real64 d_new = Rfun::clamp<Real64>(d0 + d_inc,
                                                 d_floor, env_.v_max);

        // Limit the azimuth / elevation change by the angular-rate
        // caps, then bound the elevation to the flight-path envelope.
        // The shortest signed angular difference is used so a wrap
        // across +/-pi does not produce a spurious large slew.  When a
        // speed is (near) zero its direction is undefined: on
        // acceleration from rest adopt the command heading; on
        // deceleration to rest hold the current heading.
        Real64 az_new = azc;
        Real64 el_new = elc;
        if (own_moving && cmd_moving)
        {
            const Real64 az_inc_max = env_.rate_max_azimuth * dt;
            const Real64 el_inc_max = env_.rate_max_elevation * dt;
            const Real64 az_inc = Rfun::clamp<Real64>(
                    wrap_pi_bounded(azc - az0),
                    -az_inc_max, az_inc_max);
            const Real64 el_inc = Rfun::clamp<Real64>(
                    wrap_pi_bounded(elc - el0),
                    -el_inc_max, el_inc_max);
            az_new = az0 + az_inc;
            el_new = el0 + el_inc;
        }
        else if (own_moving)
        {
            az_new = az0;
            el_new = el0;
        }
        el_new = Rfun::clamp<Real64>(el_new, env_.el_min, env_.el_max);
        az_new = wrap_pi_bounded(az_new);

        // Reconstruct the limited NED velocity from (az, el, d) for the
        // position integration and the NED cache.
        const Real64 vh_new = d_new * Rmath::cosr(el_new);
        const Real64 v_n_new = vh_new * Rmath::cosr(az_new);
        const Real64 v_e_new = vh_new * Rmath::sinr(az_new);
        const Real64 v_d_new = -d_new * Rmath::sinr(el_new);

        // Trapezoidal position update: p += (v_old + v_new) / 2 * dt,
        // using the cached pre-step NED velocity.
        const Real64 half_dt = 0.5 * dt;
        p_[0] += (v_[0] + v_n_new) * half_dt;
        p_[1] += (v_[1] + v_e_new) * half_dt;
        p_[2] += (v_[2] + v_d_new) * half_dt;

        // Commit the new spherical state and its NED cache.
        az_ = az_new;
        el_ = el_new;
        d_  = d_new;
        v_[0] = v_n_new;
        v_[1] = v_e_new;
        v_[2] = v_d_new;
    }

}  // namespace DAA
