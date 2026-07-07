
#include <Clock.h>

extern "C" Uint32 aarch64_get_cntfrq_el0();
extern "C" Uint64 aarch64_get_cntpct_el0();

namespace Zusp
{
    Uint64 Clock::get_tics()
    {
        return aarch64_get_cntpct_el0();
    }

    Uint32 Clock::get_freq()
    {
        return aarch64_get_cntfrq_el0();
    }
}
