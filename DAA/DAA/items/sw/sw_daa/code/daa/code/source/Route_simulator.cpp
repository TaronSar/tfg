// ---------------------------------------------------------------
// Route_simulator.cpp — implementation of DAA::simulate_route.
// ---------------------------------------------------------------
#include <Rfun.h>
#include <Route_cursor.h>
#include <Route_simulator.h>
#include <Route_tracker.h>
#include <Virtual_ownship.h>

namespace DAA
{

    namespace
    {

        // Maximum ratio between the cross-track pull (k_xt * D0) and the
        // unit segment tangent in build_vcmd, mirroring
        // Vpgnc::Guidance::max_d_t_ratio.  It bounds the angle the
        // velocity command may take toward the line (atan(5) ~ 78.7 deg),
        // so a large off-track error cannot fold the command back on
        // itself.
        const Real64 max_xt_ratio = 5.0;

        /// Build the velocity command for the active segment running
        /// from @p p0 to @p p1 flown at the desired speed module
        /// @p v_seg.  The command is the unit segment tangent plus a
        /// cross-track pull toward the line (gain @p k_xt, a 1/m
        /// line-attraction gain clamped so the pull never exceeds
        /// @c max_xt_ratio times the unit tangent, as in
        /// Vpgnc::Guidance::cruise_guidance); the resulting direction
        /// is then scaled to @p v_seg so the commanded speed is constant.
        void build_vcmd(const Real64* p0,
                        const Real64* p1,
                        Real64 v_seg,
                        const Real64* p_own,
                        Real64 k_xt,
                        Real64* v_cmd_out)
        {
            // Segment tangent, length and unit tangent.
            const Real64 t_n = p1[0] - p0[0];
            const Real64 t_e = p1[1] - p0[1];
            const Real64 t_d = p1[2] - p0[2];
            const Real64 len2 = t_n * t_n + t_e * t_e + t_d * t_d;

            Real64 len;
            Real64 th_n;
            Real64 th_e;
            Real64 th_d;
            if (len2 > 1.0e-12)
            {
                len = Rmath::sqrtr(len2);
                const Real64 inv_len = 1.0 / len;
                th_n = t_n * inv_len;
                th_e = t_e * inv_len;
                th_d = t_d * inv_len;
            }
            else
            {
                len = 0.0;
                th_n = 0.0;
                th_e = 0.0;
                th_d = 0.0;
            }

            // Project ownship onto the segment line.  Only the lower
            // bound is clamped (u >= 0); the upper bound is left free so
            // that once the ownship surpasses p1 the foot stays the
            // orthogonal projection on the line *extension* rather than
            // sticking at p1.  The cross-track vector is then purely
            // perpendicular to the tangent, so the tangent (forward)
            // component of the command is always preserved and the
            // velocity never turns opposite to the segment direction.
            const Real64 r_n = p_own[0] - p0[0];
            const Real64 r_e = p_own[1] - p0[1];
            const Real64 r_d = p_own[2] - p0[2];
            const Real64 u_raw = r_n * th_n + r_e * th_e + r_d * th_d;
            const Real64 u = Rfun::max<Real64>(u_raw, 0.0);
            const Real64 ptr_n = p0[0] + u * th_n;
            const Real64 ptr_e = p0[1] + u * th_e;
            const Real64 ptr_d = p0[2] + u * th_d;

            // Cross-track vector from the ownship toward the line and its
            // magnitude D0.
            const Real64 xt_n = ptr_n - p_own[0];
            const Real64 xt_e = ptr_e - p_own[1];
            const Real64 xt_d = ptr_d - p_own[2];
            const Real64 d0 = Rmath::sqrtr(xt_n * xt_n
                                         + xt_e * xt_e
                                         + xt_d * xt_d);

            // Line-attraction gain (1/m), clamped so the cross-track
            // pull (kd * D0) never exceeds max_xt_ratio times the unit
            // tangent (cf. Vpgnc::Guidance::cruise_guidance), which
            // bounds the intercept angle.  d0 > 0 whenever the clamp
            // branch is taken, so the division is safe.
            Real64 kd = k_xt;
            if ((kd * d0) > max_xt_ratio)
            {
                kd = max_xt_ratio / d0;
            }

            // Direction field = unit tangent + clamped cross-track pull,
            // then scaled to the desired segment speed so the commanded
            // speed module is exactly v_seg.
            const Real64 vf_n = th_n + kd * xt_n;
            const Real64 vf_e = th_e + kd * xt_e;
            const Real64 vf_d = th_d + kd * xt_d;
            const Real64 vf2 = vf_n * vf_n + vf_e * vf_e + vf_d * vf_d;
            if ((v_seg > 0.0) && (vf2 > 1.0e-12))
            {
                const Real64 scale = v_seg / Rmath::sqrtr(vf2);
                v_cmd_out[0] = scale * vf_n;
                v_cmd_out[1] = scale * vf_e;
                v_cmd_out[2] = scale * vf_d;
            }
            else
            {
                v_cmd_out[0] = 0.0;
                v_cmd_out[1] = 0.0;
                v_cmd_out[2] = 0.0;
            }
        }

    }  // namespace


    void simulate_route_step(Route_cursor& cursor,
                             const Route_transform& route_xf,
                             Real64 k_xt,
                             Real64 dt,
                             Virtual_ownship& own)
    {
        if (route_xf.mode == GUIDANCE_HOLD_VELOCITY)
        {
            // Stand-on / "maintain" guidance: fly the stored constant
            // NED velocity verbatim, ignoring the route for guidance.
            // The cursor is still advanced against the live position so
            // a later return-to-route resumes from the correct segment.
            // Virtual_ownship's accel limits yield a constant-velocity
            // straight line once the ownship velocity has reached the
            // held value.
            Real64 p_now[3];
            own.get_position(p_now);
            cursor.advance(p_now, route_xf);
            own.step(route_xf.velocity, dt);
        }
        else if (route_xf.mode == GUIDANCE_EXTERNAL_TRACK)
        {
            // "Minimal bearing at start" guidance: fly a single fixed
            // straight segment track_p0 -> track_p1 (NED) at the constant
            // speed track_speed captured at commit, the same way the
            // maintain mode captures its velocity.  The ownship is
            // cross-track-locked onto the line; once it surpasses
            // track_p1 the orthogonal projection continues along the
            // line extension, so the command keeps the ownship flying
            // straight in the same direction (it does not turn back).
            // The cursor is still advanced against the live position so a
            // later return-to-route resumes correctly.
            Real64 p_now[3];
            Real64 v_cmd[3];
            own.get_position(p_now);
            cursor.advance(p_now, route_xf);

            // Desired speed = the fixed segment speed carried in the
            // transform (not recomputed from the live ownship state).
            const Real64 v_seg = route_xf.track_speed;

            build_vcmd(route_xf.track_p0, route_xf.track_p1, v_seg,
                       p_now, k_xt, v_cmd);
            own.step(v_cmd, dt);
        }
        else if (cursor.has_segment())
        {
            Real64 p_now[3];
            Real64 v_cmd[3];
            Real64 p_seg0[3];
            Real64 p_seg1[3];
            Real64 v_seg = 0.0;

            own.get_position(p_now);

            // Forward-only active segment; the cursor never regresses,
            // so routes that loop back on themselves (circles,
            // racetracks) stay correctly tracked.  Endpoints are read
            // through the cursor so the raw tracker is never indexed
            // with a stale offset.
            cursor.advance(p_now, route_xf);

            // Desired speed = the target speed carried at the segment end
            // point p1 (the speed the ownship shall have when flying
            // towards that waypoint), read straight from the route rather
            // than differenced from the sampled waypoint positions, which
            // would inject finite-difference speed noise.
            cursor.point_at(0U, p_seg0, 0, route_xf);
            cursor.point_at(1U, p_seg1, &v_seg, route_xf);

            build_vcmd(p_seg0, p_seg1, v_seg, p_now, k_xt, v_cmd);
            own.step(v_cmd, dt);
        }
    }


    void simulate_route_advance(Route_cursor& cursor,
                                const Route_transform& route_xf,
                                Real64 k_xt,
                                Real64 dt_total,
                                Real64 sim_dt_max,
                                Virtual_ownship& own)
    {
        const Real64 sim_dt_safe = Rfun::max<Real64>(sim_dt_max, 1.0e-6);
        Real64 t = 0.0;
        while (t < dt_total)
        {
            Real64 dt = dt_total - t;
            if (dt > sim_dt_safe)
            {
                dt = sim_dt_safe;
            }
            simulate_route_step(cursor, route_xf, k_xt, dt, own);
            t += dt;
        }
    }

}  // namespace DAA
