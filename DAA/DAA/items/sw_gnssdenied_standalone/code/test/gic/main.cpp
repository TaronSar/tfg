#include <Uart.h>
#include <Printf.h>
#include <Core_utils.h>
#include <CortexA53/GIC.h>
#include <Hw_IO.h>
#include <Intr_vector.h>
#include <CortexA53/GIC.h>

void interrupt_handler(Uint32 CallbackRef)
{
    Uint8 core_id = Zusp::Core_utils::get_id();
    Zusp::Printf::printf("Core id: %d handling interrupt, callbacked %d\n\r", core_id, CallbackRef);
    while(1){}
}

int main()
{
    Uint8 core_id = Zusp::Core_utils::get_id();
    
    if(core_id == 0){
        Zusp::Uart::init(Zusp::uart_0, 115200, uart_0_baseaddr);

    } else{
        while(!Zusp::Uart::get_uart(Zusp::uart_0)->check_init()){}
    }

    Zusp::Printf::printf("Main Core id: %d\n\r", core_id); 
    if(core_id == 0){
//
        // Enable Distributor
        //write_register(gic_base_addr + gicd_offset + gicd_ctrl_offset, 0x01UL);
        Zusp::GIC::init_distr();
    }
    if(core_id == 0){
        //Set Handler
	    Zusp::Intr_vector::excep_vec_table[exc_id_irq_int].handler = (Zusp::Exception::Exc_handler)interrupt_handler;
	    Zusp::Intr_vector::excep_vec_table[exc_id_irq_int].data = (void *)52;
        //ENABLE IRQs at CPU
        Zusp::GIC::enable(3);
        Zusp::GIC::trigg_sec_sgi(3, 0x02);
    } 
    Zusp::Printf::printf("End Core id: %d\n\r", core_id); 
    while(1){}

    return 0;
}

