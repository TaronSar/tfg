

extern "C"{
    #include "platform.h"
    #include "xil_printf.h"
    #include "sleep.h"
}

extern "C" uint8_t init_cores();

uint8_t core_id;

int main()
{
    core_id = init_cores();

    //disable_caches();
    if(core_id == 0) {
        init_platform();
    }
    // Potentially race condition
    xil_printf("Hello World, Im the core %d\n\r", core_id);

    while(1){}
    cleanup_platform();
    return 0;
}


