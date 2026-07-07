

extern "C"{
    #include "platform.h"
    #include "xil_printf.h" //TO REMOVE
}

#include <Clock.h>
#include <Sleep.h>

int main()
{
    init_platform();

    xil_printf("Hello World, the frecuency is: %d Hz\n\r", Zusp::Clock::get_freq());
    Zusp::Sleep::sleep_ms(1000);
    xil_printf("Tick from start, %ld\n\r", Zusp::Clock::get_tics());
    Zusp::Sleep::sleep_ms(1000);
    xil_printf("Tick from start, %ld\n\r", Zusp::Clock::get_tics());
        
    cleanup_platform();
    return 0;
}

