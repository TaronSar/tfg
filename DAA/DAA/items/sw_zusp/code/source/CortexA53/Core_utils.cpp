
#include <Core_utils.h>

extern "C" Uint8 aarch64_get_affinity_el1();

namespace Zusp
{
    Uint8 Core_utils::get_id()
    {
        return aarch64_get_affinity_el1();
    }

}
