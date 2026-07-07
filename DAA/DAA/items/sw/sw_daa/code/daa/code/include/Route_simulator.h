// ---------------------------------------------------------------
// Route_simulator.h — Free function that drives a Virtual_ownship
// along a polyline route described as (position, time) samples.
//
// The route is interpreted as a sequence of straight segments
// between consecutive samples.  The route waypoints and the
// output sampling grid are decoupled: the caller may describe the
// route with a handful of waypoints and request the flown
// trajectory at an arbitrarily dense set of output times.
//
// At every integration sub-step:
//
//   * advance the active segment index while the ownship has
//     crossed the perpendicular plane at the segment's end point;
//
//   * compute a desired track position as the projection of the
//     ownship onto the active segment, clamped to the segment
//     endpoints;
//
//   * build a velocity command
//        v_cmd = clip( k_xt * (p_track - p_own)
//                      + v_seg * t_hat,
//                      |v_cmd| <= v_seg )
//     where t_hat is the unit tangent of the active segment and
//     v_seg = ||p[seg] - p[seg-1]|| / (route_t[seg] - route_t[seg-1])
//     is the expected average speed on that segment;
//
//   * apply Virtual_ownship.step(v_cmd, sim_dt) using the ownship's
//     configured along/lateral/vertical accel limits.
//
// The flown NED position is sampled at every output time
// out_t[i] and written to p_out (row-major, n_out x 3).
// p_out[0] is the initial position (== p0_ned).  Integration
// starts at out_t[0] (the initial epoch) and advances through
// the strictly ascending out_t grid; out_t[0] need not match
// route_t[0] — the segment-tracking logic is purely geometric.
//
// No allocation, no virtuals, no exceptions; the function is
// re-entrant — different threads can call it concurrently.
// ---------------------------------------------------------------
#ifndef ROUTE_SIMULATOR_H_
#define ROUTE_SIMULATOR_H_

#include <Entypes.h>
#include <Route_cursor.h>
#include <Route_tracker_fw.h>
#include <Route_transform.h>
#include <Virtual_ownship.h>

namespace DAA
{

    /// Advance @p own one integration sub-step of duration @p dt along
    /// the route held by @p cursor under the affine transform
    /// @p route_xf, using cross-track gain @p k_xt.
    ///
    /// The active segment is taken from @p cursor, which is advanced
    /// forward-only from the ownship's current position (transformed-
    /// route perpendicular-plane test); a cross-track + tangent
    /// velocity command is then applied through Virtual_ownship::step.
    /// The wrapped tracker is read only — it is *not* popped, so the
    /// caller can drive the look-ahead simulation and the real flight
    /// from the same routine.  Because the cursor never regresses,
    /// routes that loop back on themselves stay correctly tracked.
    /// No-op when the route has fewer than two waypoints.
    ///
    /// @param cursor    Forward-only active-segment cursor over the
    ///                  read-only route tracker; advanced in place.
    /// @param route_xf  Affine route transform (identity == unmodified).
    /// @param k_xt      Cross-track line-attraction gain (1/m).
    /// @param dt        Sub-step duration (s), must be > 0.
    /// @param own       Ownship integrator advanced in place.
    void simulate_route_step(Route_cursor& cursor,
                             const Route_transform& route_xf,
                             Real64 k_xt,
                             Real64 dt,
                             Virtual_ownship& own);

    /// Advance @p own by a total duration @p dt_total along the route
    /// held by @p cursor, integrating in fixed-ish sub-steps no longer
    /// than @p sim_dt_max (floored at a small epsilon).  Each sub-step
    /// calls simulate_route_step, so the tracker is read only and the
    /// cursor accumulates monotonic progress across the whole advance.
    ///
    /// @param cursor     Forward-only active-segment cursor over the
    ///                   read-only route tracker; advanced in place.
    /// @param route_xf   Affine route transform (identity == unmodified).
    /// @param k_xt       Cross-track line-attraction gain (1/m).
    /// @param dt_total   Total duration to advance (s); <= 0 is a no-op.
    /// @param sim_dt_max Maximum integration sub-step (s).
    /// @param own        Ownship integrator advanced in place.
    void simulate_route_advance(Route_cursor& cursor,
                                const Route_transform& route_xf,
                                Real64 k_xt,
                                Real64 dt_total,
                                Real64 sim_dt_max,
                                Virtual_ownship& own);

}  // namespace DAA

#endif  // ROUTE_SIMULATOR_H_
