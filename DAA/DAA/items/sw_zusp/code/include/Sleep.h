#ifndef ZUSP_SLEEP_H_
#define ZUSP_SLEEP_H_

#include <Clock.h> 

namespace Zusp
{
    class Sleep
    {
        public:
            static void sleep_us(Uint32 usec); 
            static void sleep_ms(Uint32 msec);

        private:
            Sleep(); ///< = delete
            Sleep(const Sleep& orig); ///< = delete
            ~Sleep(); ///< = delete
            Sleep& operator=(const Sleep& orig); ///< = delete

    };
}

#endif