// ---------------------------------------------------------------
// Route_tracker.cpp — implementation of the heap-backed circular
// waypoint tracker declared in Route_tracker.h.
//
// Memory model: one malloc-allocated row-major waypoint array where
// each slot stores [N, E, D, speed].  Using malloc/free
// (not operator new) keeps the SIL DLL free of libgcc_eh.
// ---------------------------------------------------------------
#include <Route_tracker.h>

#include <Route_cursor.h>

#include <cstdlib>

namespace DAA
{

    namespace
    {
        static const Route_transform route_transform_identity;
    }

    Route_tracker::Route_tracker(Uint32 capacity) :
            buf_(0),
            capacity_(capacity),
            head_(0U),
            count_(0U)
    {
        if (capacity_ != 0U)
        {
            const Uint32 n_pdt = capacity_ * 4U;
            buf_ = static_cast<Real64*>(std::malloc(n_pdt * sizeof(Real64)));
            if (buf_ == 0)
            {
                capacity_ = 0U;
            }
        }
    }

    Route_tracker::~Route_tracker()
    {
        if (buf_ != 0) { std::free(buf_); buf_ = 0; }
    }

    bool Route_tracker::push(const Real64* p_ned, Real64 speed)
    {
        bool ok = false;
        if ((count_ < capacity_) && (buf_ != 0))
        {
            const Uint32 tail = (head_ + count_) % capacity_;
            Real64* dst = &buf_[tail * 4U];
            dst[0] = p_ned[0];
            dst[1] = p_ned[1];
            dst[2] = p_ned[2];
            dst[3] = speed;
            count_ += 1U;
            ok = true;
        }
        return ok;
    }

    Uint32 Route_tracker::push_batch(const Real64* pdt_n4,
                                     Uint32 n)
    {
        Uint32 pushed = 0U;
        bool   keep_going = true;
        while (keep_going && (pushed < n))
        {
            const Real64* pdt = &pdt_n4[pushed * 4U];
            const bool ok = push(pdt, pdt[3]);
            if (ok)
            {
                pushed += 1U;
            }
            else
            {
                keep_going = false;
            }
        }
        return pushed;
    }

    Route_cursor Route_tracker::make_cursor() const
    {
        return Route_cursor(buf_, capacity_, head_, count_);
    }

    void Route_tracker::pop_to_cursor(const Route_cursor& cursor)
    {
        // ---- Adopt the cursor's view as the new head --------------
        // The cursor advanced its head forward over the waypoints the
        // ownship surpassed, leaving cursor.count_ waypoints from that
        // head onward.  Adopting its head and count drops exactly the
        // surpassed waypoints.
        head_ = cursor.head_;
        count_ = cursor.count_;
    }

    bool Route_tracker::project_active(const Real64* p_now_ned,
                                       Real64*       p_out) const
    {
        bool ok = false;
        if (count_ != 0U)
        {
            // Advance a local cursor — a non-mutating view over the ring
            // — forward from the current head to the segment the ownship
            // at p_now_ned is actually abeam of, scanning the *raw*
            // route (identity transform).  The tracker's own head is left
            // untouched: only pop_to_cursor() consumes waypoints, and it
            // is driven by the (possibly shifted) guidance cursor so the
            // flown route stays identical to the predicted one.  This
            // keeps the reported track point on the ownship's true
            // along-route progress even when an active lateral shift makes
            // the guidance head lag behind the raw route.
            Route_cursor cursor = make_cursor();
            cursor.advance(p_now_ned, route_transform_identity);

            if (!cursor.has_segment())
            {
                // Only the head waypoint remains — best we can do.
                cursor.point_at(0U, p_out, 0, route_transform_identity);
            }
            else
            {
                Real64 p0[3];
                Real64 p1[3];
                cursor.point_at(0U, p0, 0, route_transform_identity);
                cursor.point_at(1U, p1, 0, route_transform_identity);
                const Real64 ux = p1[0] - p0[0];
                const Real64 uy = p1[1] - p0[1];
                const Real64 uz = p1[2] - p0[2];
                const Real64 denom = (ux * ux) + (uy * uy) + (uz * uz);
                Real64 t = 0.0;
                if (denom > 1.0e-12)
                {
                    const Real64 vx = p_now_ned[0] - p0[0];
                    const Real64 vy = p_now_ned[1] - p0[1];
                    const Real64 vz = p_now_ned[2] - p0[2];
                    t = ((vx * ux) + (vy * uy) + (vz * uz)) / denom;
                    if (t < 0.0) { t = 0.0; }
                    else if (t > 1.0) { t = 1.0; }
                }
                p_out[0] = p0[0] + (t * ux);
                p_out[1] = p0[1] + (t * uy);
                p_out[2] = p0[2] + (t * uz);
            }
            ok = true;
        }
        return ok;
    }

}  // namespace DAA
