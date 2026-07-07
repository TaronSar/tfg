#include "Cache.h"

#include "Entypes.h"

extern "C" void disable_dcache(void);
extern "C" Uint8 status_dcache(void);

namespace Zusp
{
    void Dcache::disable(void)
    {
        disable_dcache();
    }

    bool Dcache::enabled(void)
    {
        bool result = false;

        if(status_dcache() != 0)
        {
            result = true;
        }
        return result;
    }
}

