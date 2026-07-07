#include <Conflict_prediction.h>

#include <Rvector3.h>

namespace Ver
{

    using namespace Maverick;

    Conflict_prediction::Conflict_prediction()
    {
    }

    Real Conflict_prediction::Cyllinder_distance::compute_at(const Real t) const
    {
        // d = P + v*t
        Rvector3 d;
        d.copy(p);
        d.lincmb_add(t, v);

        // Vertical and horizontal cylinder distances
        const Real d_cyl_z = Rmath::fabsr(d[Ivector3<Real>::vz]) / cyl_h;
        const Real d_cyl_xy = d.norm2xy() / cyl_d;

        // Return maximum
        return Rfun::max<Real>(d_cyl_z, d_cyl_xy);
    }

    Conflict_prediction::Tcpa_selector::Tcpa_selector(const Conflict_prediction::Cyllinder_distance& cpi0,
                                                      const Real tmax0) :
        cpi(cpi0),
        tmax(tmax0),
        dist(cpi0.compute_at(0.0F)),
        t(0.0F)
    {
    }

    void Conflict_prediction::Tcpa_selector::push(const Real t0)
    {
        if ((0.0F <= t0) && (t0 <= tmax))
        {
            const Real dist0 = cpi.compute_at(t0);
            if ((dist0 < dist) || ((dist0 == dist) && (t0 < t)))
            {
                dist = dist0;
                t = t0;
            }
        }
    }

    Real Conflict_prediction::compute_tcpa(const Conflict_prediction::Cyllinder_distance& cpi, const Real tmax)
    {
        // Point of interest 0: t = 0
        Conflict_prediction::Tcpa_selector tcpa_sel(cpi, tmax);

        // Point of interest 1: t = tmax
        tcpa_sel.push(tmax);

        // Point of interest 2: Minimizing vertical component
        static const Real eps_vz = 1.0E-6F;
        const Real vz = cpi.v[Ivector3<Real>::vz];
        const Real pz = cpi.p[Ivector3<Real>::vz];
        if (Rmath::fabsr(vz) > eps_vz)
        {
            tcpa_sel.push(-pz / vz);
        }

        // Point of interest 3: Minimizing horizontal component
        static const Real eps_vxy2 = 1.0E-12F;
        const Real nvxy2 = cpi.v.norm22();
        const Real pxy_vxy = cpi.p.dotxy(cpi.v);
        if (nvxy2 > eps_vxy2)
        {
            tcpa_sel.push(-pxy_vxy / nvxy2);
        }

        // Up to two more points of interest (4 and 5), result of the solutions of the quadratic equation (a, b and c)
        const Real h2 = cpi.cyl_h*cpi.cyl_h;
        const Real d2 = cpi.cyl_d*cpi.cyl_d;
        const Real a = ((vz*vz) / h2) - (nvxy2 / d2);
        const Real b = Const::TWO*(((pz*vz) / h2) - (pxy_vxy / d2));
        const Real c = ((pz*pz) / h2) - (cpi.p.norm22() / d2);

        static const Real eps_a = 1.0E-6F;
        if (Rmath::fabsr(a) > eps_a)
        {
            const Real discriminate = (b*b) - (Const::FOUR*a*c);
            if (discriminate >= 0.0F)
            {
                // If discriminate is zero it is fine adding two times the same point
                const Real sqrt_discriminate = Rmath::sqrtr(discriminate);
                const Real two_a = Const::TWO*a;
                tcpa_sel.push((-b + sqrt_discriminate) / two_a);
                tcpa_sel.push((-b - sqrt_discriminate) / two_a);
            }
        }
        else
        {
            static const Real eps_b = 1.0E-6F;
            if (Rmath::fabsr(b) > eps_b)
            {
                tcpa_sel.push(-c / b);
            }
        }

        return tcpa_sel.t;
    }

    Real Conflict_prediction::compute_risk(const Conflict_prediction::Cyllinder_distance& cpi,
                                           const Maverick::Irvector3& upo,
                                           const Maverick::Irvector3& upi,
                                           const Maverick::Irvector3& uvo,
                                           const Maverick::Irvector3& uvi,
                                           const Real tcpa,
                                           const Real sigma,
                                           const Real factor)
    {
        Conflict_prediction::Cyllinder_distance cpi_risk;
        cpi_risk.p.copy(cpi.p);
        cpi_risk.v.copy(cpi.v);

        // Horizontal part
        const Real cyl_d_plus = (cpi.cyl_d +
                upo.norm2xy() + upi.norm2xy() +
                ((uvo.norm2xy() + uvi.norm2xy()) * tcpa)) * sigma;

        cpi_risk.cyl_d = Rfun::min<Real>(cyl_d_plus, cpi.cyl_d*factor);

        // Vertical part
        const Real cyl_h_plus = (cpi.cyl_h +
                Rmath::fabsr(upo[Ivector3<Real>::vz]) + Rmath::fabsr(upi[Ivector3<Real>::vz]) +
                ((Rmath::fabsr(uvo[Ivector3<Real>::vz]) + Rmath::fabsr(uvi[Ivector3<Real>::vz])) * tcpa)) * sigma;

        cpi_risk.cyl_h = Rfun::min<Real>(cyl_h_plus, cpi.cyl_h*factor);


        // Return cylinder distance
        return cpi_risk.compute_at(tcpa);
    }

}
