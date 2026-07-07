#ifndef ZUSP_CLOCK_H_
#define ZUSP_CLOCK_H_

#include <Entypes.h> //from Vlibs

namespace Zusp
{
    class Clock
    {
        public:
            static Uint64 get_tics(); 
            static Uint32 get_freq();

        private:
            Clock(); ///< = delete
            Clock(const Clock& orig); ///< = delete
            ~Clock(); ///< = delete
            Clock& operator=(const Clock& orig); ///< = delete

    };
}

#endif