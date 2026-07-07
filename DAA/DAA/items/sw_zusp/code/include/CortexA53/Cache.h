#ifndef ZUSP_Dcache_H_
#define ZUSP_Dcache_H_

#include <Entypes.h> //from Vlibs

namespace Zusp
{
    class Dcache
    {
        public:
        static void disable();
        static bool enabled();


        private:
            Dcache(); ///< = delete
            Dcache(const Dcache& orig); ///< = delete
            ~Dcache(); ///< = delete
            Dcache& operator=(const Dcache& orig); ///< = delete

    };
}

#endif

