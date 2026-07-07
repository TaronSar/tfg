#ifndef ZUSP_CORE_UTILS_H_
#define ZUSP_CORE_UTILS_H_

#include <Entypes.h> //from Vlibs
#include <CortexA53/Core_def.h> 

namespace Zusp
{
    class Core_utils
    {
        public:
            static Uint8 get_id(); 

        private:
            Core_utils(); ///< = delete
            Core_utils(const Core_utils& orig); ///< = delete
            ~Core_utils(); ///< = delete
            Core_utils& operator=(const Core_utils& orig); ///< = delete

    };
}

#endif