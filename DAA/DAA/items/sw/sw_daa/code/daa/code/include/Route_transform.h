// ---------------------------------------------------------------
// Route_transform.h — guidance modifier applied on the fly by
// Route_tracker queries and the route simulator.
//
// The `mode` field selects how the velocity command is produced:
//
//   * GUIDANCE_TRACK_ROUTE — follow the stored route.  Every waypoint
//     position is translated by `shift` and every segment target speed
//     is multiplied by `speed_scale`, so a tracker behaves as if its
//     stored route were modified, without mutating it.
//
//   * GUIDANCE_HOLD_VELOCITY — ignore the route and fly the constant
//     NED `velocity` (stand-on / "maintain" maneuver).
//
//   * GUIDANCE_EXTERNAL_TRACK — ignore the route and fly a fixed
//     straight segment from `track_p0` to `track_p1` (NED m) at the
//     constant speed `track_speed` (m/s, captured at commit),
//     cross-track-locked onto the line and continuing straight past
//     `track_p1`.  Used by the "minimal bearing at start" avoidance
//     family, where the segment end point is the predicted intruder
//     position at the CPA offset by the configured safety margin to
//     the right / left / above / below.
//
// The identity transform is
//   { GUIDANCE_TRACK_ROUTE, {0, 0, 0}, 1.0, {0, 0, 0}, {0,0,0}, {0,0,0}, 0.0 }.
// ---------------------------------------------------------------
#ifndef ROUTE_TRANSFORM_H_
#define ROUTE_TRANSFORM_H_

#include <Entypes.h>

namespace DAA
{

    /// Guidance mode selecting how the velocity command is built.
    enum Guidance_mode
    {
        GUIDANCE_TRACK_ROUTE   = 0,  ///< Follow the route (shift + speed_scale).
        GUIDANCE_HOLD_VELOCITY = 1,  ///< Fly the constant `velocity`.
        GUIDANCE_EXTERNAL_TRACK = 2  ///< Fly the straight `track_p0`->`track_p1` segment.
    };

    struct Route_transform
    {
        Guidance_mode mode;  ///< Active guidance mode.
        Real64 shift[3];     ///< [TRACK_ROUTE] NED increment per waypoint (m).
        Real64 speed_scale;  ///< [TRACK_ROUTE] segment target-speed multiplier.
        Real64 velocity[3];  ///< [HOLD_VELOCITY] NED velocity to hold (m/s).
        Real64 track_p0[3];  ///< [EXTERNAL_TRACK] segment start (NED m).
        Real64 track_p1[3];  ///< [EXTERNAL_TRACK] segment end (NED m).
        Real64 track_speed;  ///< [EXTERNAL_TRACK] constant segment speed (m/s).

        /// Default-construct the identity transform: track the route
        /// verbatim ({ GUIDANCE_TRACK_ROUTE, {0, 0, 0}, 1.0, {0, 0, 0},
        /// {0, 0, 0}, {0, 0, 0}, 0.0 }).
        Route_transform();
    };

}  // namespace DAA

#endif  // ROUTE_TRANSFORM_H_
