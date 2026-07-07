// ---------------------------------------------------------------
// Route_cursor.h — lightweight, copyable forward-only view over a
// Route_tracker's waypoint ring, used by the route simulator to
// remember which segment the (projected) ownship is flying between
// sub-steps.
//
// A plain perpendicular-plane crossing scan that always restarts
// from the route head can jump *backwards* whenever the route loops
// back close to an earlier segment (circles, racetracks, self-
// intersections).  Route_cursor keeps its own head on the active
// segment and only ever scans forward from it, guaranteeing
// monotonic progression along the polyline.
//
// The cursor is a *view*: it holds a pointer into the tracker's ring
// buffer plus its own head/count, so it is freely copyable and its
// state is trivial to transfer.  It never mutates the tracker; the
// tracker must outlive the cursor and must not be modified while a
// cursor over it is in use.  Build one with
// Route_tracker::make_cursor().
//
// No allocation, no virtuals, no exceptions.
// ---------------------------------------------------------------
#ifndef ROUTE_CURSOR_H_
#define ROUTE_CURSOR_H_

#include <Entypes.h>
#include <Route_transform.h>

namespace DAA
{

    class Route_cursor
    {
    public:
        /// Construct an empty view (no waypoints).  Mainly so a cursor
        /// can be stored and assigned later; build a populated cursor
        /// with Route_tracker::make_cursor().
        Route_cursor();

        // Copyable and assignable (implicit): a cursor is a small
        // value holding a buffer pointer, the ring capacity and its
        // own head/count.

        /// True when the view holds at least one full segment
        /// (>= 2 waypoints), i.e. point_at(0) / point_at(1) address a
        /// valid active segment.
        bool has_segment() const;

        /// Read a waypoint of the cursor's active segment, transformed
        /// by @p xf.  Offsets are relative to the active segment, so
        /// the cursor never exposes the raw ring indexing.
        ///
        /// @param rel     0 == active segment start, 1 == its end.
        /// @param p_out   [3] receives the NED position (m); may be
        ///                NULL to skip.
        /// @param v_out   Receives the segment target speed (m/s) stored
        ///                at the addressed waypoint; may be NULL to skip.
        /// @param xf      Affine route transform: @c xf.shift is added
        ///                to the position and @c xf.speed_scale
        ///                multiplies the speed.  Pass the identity
        ///                transform for the unmodified route.
        /// @return true when the addressed waypoint exists.
        bool point_at(Uint32 rel, Real64* p_out, Real64* v_out,
                      const Route_transform& xf) const;

        /// Advance the cursor's head forward to the segment the ownship
        /// at @p p_now_ned is currently flying, under the affine route
        /// transform @p xf.  The cursor never moves backwards, so a
        /// route that loops near an earlier segment keeps progressing.
        /// The head stops on the last full segment so point_at(1) stays
        /// valid.  No-op when fewer than two waypoints remain.
        ///
        /// @param p_now_ned [3] current NED ownship position (ft).
        /// @param xf        Affine route transform: @c xf.shift is
        ///                  added to every waypoint before the
        ///                  perpendicular-plane crossing test;
        ///                  @c xf.speed_scale is ignored.  Pass the
        ///                  identity transform for the unmodified route.
        void advance(const Real64* p_now_ned,
                     const Route_transform& xf);

    private:
        // Only the tracker mints populated cursors and reads the view
        // state back (Route_tracker::make_cursor / pop_to_cursor).
        friend class Route_tracker;

        Route_cursor(const Real64* buf, Uint32 capacity,
                     Uint32 head, Uint32 count);

        const Real64* buf_;   // ring data [N,E,D,dt] per slot; not owned.
        Uint32 capacity_;     // ring capacity (slots).
        Uint32 head_;         // ring index of the active segment start.
        Uint32 count_;        // waypoints from head_ to the route end.
    };

}  // namespace DAA

#endif  // ROUTE_CURSOR_H_
