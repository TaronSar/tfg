#ifndef CONFLICT_PREDICTION_H_
#define CONFLICT_PREDICTION_H_

#include <Rvector3.h>

namespace Ver
{

    class Conflict_prediction
    {
    public:
        Conflict_prediction();

        struct Cyllinder_distance
        {
            Maverick::Rvector3 p;
            Maverick::Rvector3 v;
            Real cyl_h;
            Real cyl_d;

            Real compute_at(const Real t) const;
        };

        struct Tcpa_selector
        {
            Tcpa_selector(const Conflict_prediction::Cyllinder_distance& cpi0, const Real tmax0);
            void push(const Real t0);

            const Conflict_prediction::Cyllinder_distance& cpi;
            const Real tmax;
            Real dist;
            Real t;
        };

        static Real compute_tcpa(const Conflict_prediction::Cyllinder_distance& cpi, const Real tmax);

        static Real compute_risk(const Conflict_prediction::Cyllinder_distance& cpi,
                                 const Maverick::Irvector3& upo,
                                 const Maverick::Irvector3& upi,
                                 const Maverick::Irvector3& uvo,
                                 const Maverick::Irvector3& uvi,
                                 const Real tcpa,
                                 const Real sigma,
                                 const Real factor);


    private:

    };

}

#endif
