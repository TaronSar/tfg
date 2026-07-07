#include <UART.h>
#include <Printf.h>
#include <Core_utils.h>
#include <Irq_manager.h>


void interrupt_handler(Uint32 CallbackRef)
{
    Uint8 core_id = Zusp::Core_utils::get_id();
    Zusp::Printf::printf("Core id: %d handling interrupt, callbacked %d\n\r", core_id, CallbackRef);
    while(1){}
}

Zusp::Irq_manager::Irq_handler core2_handler;

int main()
{
    Uint8 core_id = Zusp::Core_utils::get_id();
    
    if(core_id == 0){
        Zusp::UART::init(Zusp::UART_0, 115200, UART_0_baseaddr);

    } else{
        while(!Zusp::UART::get_UART(Zusp::UART_0)->check_init()){}
    }

    Zusp::Printf::printf("Main Core id: %d\n\r", core_id); 
    if(core_id == 0){
        core2_handler.handler = (Zusp::Irq_manager::Handler_ptr)interrupt_handler;
        core2_handler.data = (void*)65;

        Zusp::Irq_manager irq_core2(3, 0x02, core2_handler);

        Uint8 dbg_error = irq_core2.signal();
        if(dbg_error != 0) Zusp::Printf::printf("Error id: %d\n\r", dbg_error);
    } 
    Zusp::Printf::printf("End Core id: %d\n\r", core_id); 
    while(1){}

    return 0;
}

