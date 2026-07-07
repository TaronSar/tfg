// ---------------------------------------------------------------
// Route_cursor.cpp — implementation of DAA::Route_cursor.
// ---------------------------------------------------------------
#include <Route_cursor.h>

namespace DAA
{

    Route_cursor::Route_cursor() :
            buf_(0),
            capacity_(0U),
            head_(0U),
            count_(0U)
    {
    }

    Route_cursor::Route_cursor(const Real64* buf, Uint32 capacity,
                               Uint32 head, Uint32 count) :
            buf_(buf),
            capacity_(capacity),
            head_(head),
            count_(count)
    {
    }

    bool Route_cursor::has_segment() const
    {
        return count_ >= 2U;
    }

    bool Route_cursor::point_at(Uint32 rel, Real64* p_out, Real64* v_out,
                                const Route_transform& xf) const
    {
        bool ok = false;
        if (rel < count_)
        {
            // head_ < capacity_ and rel < count_ <= capacity_, so
            // head_ + rel < 2*capacity_: a single conditional subtraction
            // is equivalent to the modulo and avoids an integer division
            // on the hot path.
            Uint32 ring = head_ + rel;
            if (ring >= capacity_)
            {
                ring -= capacity_;
            }
            const Real64* src = &buf_[ring * 4U];
            if (p_out != 0)
            {
                p_out[0] = src[0] + xf.shift[0];
                p_out[1] = src[1] + xf.shift[1];
                p_out[2] = src[2] + xf.shift[2];
            }
            if (v_out != 0)
            {
                *v_out = src[3] * xf.speed_scale;
            }
            ok = true;
        }
        return ok;
    }

    void Route_cursor::advance(const Real64* p_now_ned,
                               const Route_transform& xf)
    {
        // Scan forward only, never regressing, so a route that loops
        // back near an earlier segment keeps progressing.  Move the
        // head off the active segment whenever the ownship has crossed
        // the perpendicular plane at the segment's (transformed) end,
        // and stop on the last full segment (count_ == 2) so point_at(1)
        // always addresses a valid segment end.
        //
        // The route shift cancels in the segment direction n = p1 - p0
        // and only displaces the plane through the ownship term, so it
        // is folded once into p_rel = p_now - shift here; the per-segment
        // work then reads the raw ring slots with no transform, no array
        // copies and no modulo.
        const Real64 p_rel_n = p_now_ned[0] - xf.shift[0];
        const Real64 p_rel_e = p_now_ned[1] - xf.shift[1];
        const Real64 p_rel_d = p_now_ned[2] - xf.shift[2];

        bool keep_going = (count_ > 2U);
        while (keep_going)
        {
            // Raw slot pointers for the active segment endpoints; the
            // end index wraps with one conditional subtraction.
            Uint32 ring1 = head_ + 1U;
            if (ring1 >= capacity_)
            {
                ring1 -= capacity_;
            }
            const Real64* s0 = &buf_[head_ * 4U];
            const Real64* s1 = &buf_[ring1 * 4U];

            // Plane at the segment end s1 with normal n = s1 - s0.
            const Real64 n_n = s1[0] - s0[0];
            const Real64 n_e = s1[1] - s0[1];
            const Real64 n_d = s1[2] - s0[2];

            // s = dot((p_now - shift) - s1, n).
            const Real64 d_n = p_rel_n - s1[0];
            const Real64 d_e = p_rel_e - s1[1];
            const Real64 d_d = p_rel_d - s1[2];
            const Real64 s = (d_n * n_n) + (d_e * n_e) + (d_d * n_d);

            if (s < 0.0)
            {
                keep_going = false;
            }
            else
            {
                head_ = ring1;
                --count_;
                keep_going = (count_ > 2U);
            }
        }
    }

}  // namespace DAA
