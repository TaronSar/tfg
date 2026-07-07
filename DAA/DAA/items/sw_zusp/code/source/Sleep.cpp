
#include <Sleep.h>

namespace Zusp
{
    void Sleep::sleep_us(Uint32 usec){
        Uint64 t_cur = Clock::get_tics();
        Uint64 t_end;
        Uint32 clk_freq = Clock::get_freq();
        Uint32 counts_per_usec = ((clk_freq + 500000)/1000000); //Xilinx ARMVv8/64bit/sleep.c v9.0, line 51

        t_end = t_cur + (Uint64)(usec * counts_per_usec);

        do{
            t_cur = Clock::get_tics();
        }while(t_end > t_cur);
    } 

    void Sleep::sleep_ms(Uint32 msec){
        Sleep::sleep_us(msec * 1000);
    }
}
