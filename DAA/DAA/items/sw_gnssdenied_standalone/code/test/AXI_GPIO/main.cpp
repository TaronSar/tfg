#include <Printf.h>
#include <GPIO.h>
#include <AXI_GPIO.h>
#include <Sleep.h>

int main()
{
    /// Initialize UART0 - printf
    Zusp::UART::init(Zusp::UART_0, 115200U, UART_0_baseaddr);

    /// Wait for device initialization
    while (!Zusp::UART::get_UART(Zusp::UART_0)->check_init())
    {
        ;
    }

    static const Uint64 addr = 0x80000000U;

    static const Uint16 led_pin_1 = 0;
    static const Uint16 led_pin_2 = 1;
    static const Uint16 led_pin_3 = 2;
    static const Uint16 led_pin_4 = 3;
    static const Uint16 button_1 = 0;
    static const Uint16 button_2 = 1;
    static const Uint16 button_3 = 2;
    static const Uint16 button_4 = 3;
    static const Uint16 button_5 = 4;

    Zusp::AXI_GPIO axi_gpio(addr, 32U, 32U);

    Zusp::Printf::printf("register_addr: 0x%x\n", axi_gpio.get_register(Zusp::GPIO_2));

    Zusp::AXI_GPIO_err err = Zusp::err_ok;

    err = axi_gpio.set_pin(led_pin_1, Zusp::GPIO_2);
    err = axi_gpio.set_pin(led_pin_2, Zusp::GPIO_2);
    err = axi_gpio.set_pin(led_pin_3, Zusp::GPIO_2);
    err = axi_gpio.set_pin(led_pin_4, Zusp::GPIO_2);

    Zusp::Printf::printf("err: %u\n", static_cast<Uint8>(err));

    Zusp::Printf::printf("register_addr: 0x%x\n", axi_gpio.get_register(Zusp::GPIO_2));

    Zusp::Sleep::sleep_ms(1000);

    err = axi_gpio.clear_pin(led_pin_1, Zusp::GPIO_2);
    err = axi_gpio.clear_pin(led_pin_2, Zusp::GPIO_2);
    err = axi_gpio.clear_pin(led_pin_3, Zusp::GPIO_2);
    err = axi_gpio.clear_pin(led_pin_4, Zusp::GPIO_2);

    Zusp::Printf::printf("err: %u\n", static_cast<Uint8>(err));

    Zusp::Printf::printf("register_addr: 0x%x\n", axi_gpio.get_register(Zusp::GPIO_2));

    Zusp::Sleep::sleep_ms(1000);
    
    err = axi_gpio.set_register(0xF, Zusp::GPIO_2);

    Zusp::Printf::printf("err: %u\n", static_cast<Uint8>(err));

    Zusp::Printf::printf("register_addr: 0x%x\n", axi_gpio.get_register(Zusp::GPIO_2));

    Zusp::Sleep::sleep_ms(2000);

    err = axi_gpio.set_pin(32U, Zusp::GPIO_2);

    Zusp::Printf::printf("err: %u\n", static_cast<Uint8>(err));

    while (true)
    {
        Zusp::Printf::printf("register_addr: 0x%x\n", axi_gpio.get_register(Zusp::GPIO_0));
    }

    Zusp::Printf::printf("Terminado.\n");

    return 0;
}
