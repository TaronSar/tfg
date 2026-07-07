#include <Entypes.h>
#include <Printf.h>
#include <Uart.h>
#include <Sleep.h>
#include <Core_utils.h>


Uint8 i;

int main()
{
    int core_id;
    core_id = Zusp::Core_utils::get_id();

    //disable_caches();
    if(core_id == 0) {
        Zusp::Uart::init(Zusp::uart_0, 115200, uart_0_baseaddr);
    }

    while(!Zusp::Uart::check_init(Zusp::uart_0)){}

    Zusp::Uart* uart0 = Zusp::Uart::get_uart(Zusp::uart_0);
    for(i = 30; i < 100; i++){

        uart0->send_byte(((Uint8)core_id+0x30));
        uart0->send_byte((Uint8)0x3A);
        uart0->send_byte(i);
        uart0->send_byte((Uint8)0x20);
        Zusp::Sleep::sleep_ms(1000);
    }

    return 0;
}


