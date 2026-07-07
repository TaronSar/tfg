// ---------------------------------------------------------------
// Route_tracker.h — Stateful tracker of baseline waypoints ahead
// of an ownship, used by the avoidance loop to:
//
//   * drop baseline waypoints the ownship has already passed, kept in
//     step with a Route_cursor via pop_to_cursor(),
//   * hand out forward-only Route_cursor views for the Virtual_ownship
//     route simulator (shift / return-to-route),
//   * project the ownship onto the active route segment.
//
// Storage is heap-allocated at construction (single malloc); no STL,
// no exceptions, no virtuals.  One instance per simulation thread.
// ---------------------------------------------------------------
#ifndef ROUTE_TRACKER_H_
#define ROUTE_TRACKER_H_

#include <Entypes.h>
#include <Route_cursor_fw.h>
#include <Route_transform.h>

namespace DAA
{

    class Route_tracker
    {
    public:
        /// Construct an empty tracker with the given waypoint capacity
        /// (>= 2 recommended; 0 yields a tracker that always fails to
        /// push).
        explicit Route_tracker(Uint32 capacity);

        /// Release the internal storage.
        ~Route_tracker();

        // ---- Modifiers --------------------------------------------

        /// Append one waypoint at the tail with its target speed.
        ///
        /// @param p_ned [3] NED position (m).
        /// @param speed Target speed (m/s) the ownship shall have when
        ///              flying *towards* this waypoint (i.e. the speed
        ///              of the segment that ends at it).  The speed of
        ///              the first waypoint is meaningless (no segment
        ///              leads to it) and conventionally set to 0.
        /// @return true on success, false if the buffer is full.
        bool push(const Real64* p_ned, Real64 speed);

        /// Append n waypoints from a row-major (n x 4) array where each
        /// row is [N, E, D, speed].  Pushing stops at the first
        /// full-buffer failure.
        /// @return number of waypoints actually pushed.
        Uint32 push_batch(const Real64* pdt_n4,
                          Uint32 n);

        // ---- Cursor -----------------------------------------------

        /// Build a forward-only view (Route_cursor) over this tracker,
        /// parked on the current head segment.  The returned cursor
        /// holds a pointer into this tracker's waypoint ring plus its
        /// own head/count, so it is freely copyable; this tracker must
        /// outlive it and must not be modified while it is in use.
        Route_cursor make_cursor() const;

        /// Drop the head waypoints the @p cursor has advanced past,
        /// realigning the tracker head with the cursor's active
        /// segment.  The cursor is a view obtained from make_cursor()
        /// on this tracker; its advanced head and remaining count are
        /// adopted as the tracker's new head and size, so the number of
        /// waypoints dropped equals how far the cursor moved forward.
        ///
        /// Unlike a fresh head scan, this trusts the cursor's
        /// forward-only progress, so routes that loop back on
        /// themselves stay correctly aligned.
        ///
        /// @param cursor  Forward-only view over this tracker, as
        ///                returned by make_cursor() and then advanced.
        void pop_to_cursor(const Route_cursor& cursor);

        // ---- Query ------------------------------------------------

        /// Project @p p_now_ned onto the upcoming route segment
        /// (head → head+1) and copy the foot of perpendicular into
        /// @p p_out.  The projection parameter is clamped to [0, 1]
        /// so the result always lies on the segment itself.
        ///
        /// When the tracker has only one remaining waypoint the
        /// head itself is returned; when empty the function fails.
        ///
        /// @return true if the tracker is non-empty.
        bool project_active(const Real64* p_now_ned,
                            Real64*       p_out) const;

    private:
        // Non-copyable.
        Route_tracker(const Route_tracker&);
        Route_tracker& operator=(const Route_tracker&);

        Real64* buf_;          // capacity_ * 4 doubles (row-major [N,E,D,speed]).
        Uint32  capacity_;
        Uint32  head_;         // ring index of the oldest waypoint.
        Uint32  count_;        // number of stored waypoints.
    };

}  // namespace DAA

#endif  // ROUTE_TRACKER_H_
