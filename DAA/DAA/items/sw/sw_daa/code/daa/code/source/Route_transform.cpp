// ---------------------------------------------------------------
// Route_transform.cpp — out-of-line definition of the default
// (identity) Route_transform constructor declared in
// Route_transform.h.
// ---------------------------------------------------------------
#include <Route_transform.h>

namespace DAA
{

    Route_transform::Route_transform() :
            mode(GUIDANCE_TRACK_ROUTE),
            speed_scale(1.0)
    {
        shift[0] = 0.0;
        shift[1] = 0.0;
        shift[2] = 0.0;
        velocity[0] = 0.0;
        velocity[1] = 0.0;
        velocity[2] = 0.0;
        track_p0[0] = 0.0;
        track_p0[1] = 0.0;
        track_p0[2] = 0.0;
        track_p1[0] = 0.0;
        track_p1[1] = 0.0;
        track_p1[2] = 0.0;
        track_speed = 0.0;
    }

}  // namespace DAA
