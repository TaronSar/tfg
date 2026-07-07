#include <Printf.h>
#include <Sleep.h>
#include <Core_utils.h>
#include <UART.h>


int main()
{
    Uint8 core_id = Zusp::Core_utils::get_id();
    
    if(core_id == 0)
    {
        Zusp::UART::init(Zusp::UART_0, 115200U, UART_0_baseaddr);
    }

    //  Assure UART is initialized
    while(!Zusp::UART::get_UART(Zusp::UART_0)->check_init())
    {
        ;
    }

 
    while(1)
    {
        Zusp::Printf::printf("%d core printing message.\n",core_id);
        Zusp::Sleep::sleep_ms(5000);
    }

    return 0;
}