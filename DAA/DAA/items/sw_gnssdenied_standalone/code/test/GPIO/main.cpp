#include <Printf.h>
#include <GPIO.h>
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

    static const Uint16 led_pin_1 = 0;
    static const Uint16 led_pin_2 = 1;
    static const Uint16 button_1  = 0;
    static const Uint16 button_2  = 1;

    Zusp::GPIO gpio_but(Zusp::GPIO_bank3);
    Zusp::GPIO gpio_led(Zusp::GPIO_bank3);

    gpio_but.config_pin(button_1, Zusp::GPIO_input);
    gpio_but.config_pin(button_2, Zusp::GPIO_input);
    gpio_led.config_pin(led_pin_1, Zusp::GPIO_output);
    gpio_led.config_pin(led_pin_2, Zusp::GPIO_output);

    
    while (true)
    {
        Uint32 button_1_state = gpio_but.get_val(button_1);
        Uint32 button_2_state = gpio_but.get_val(button_2);

        if(button_1_state == 1)
        {
            Zusp::Printf::printf("Boton 1 presionado.\n");
            gpio_led.set_high(led_pin_1);
        }
        else
        {
            gpio_led.set_low(led_pin_1);
        }
        if(button_2_state == 1)
        {
            Zusp::Printf::printf("Boton 2 presionado.\n");
            gpio_led.set_high(led_pin_2);
        }
        else
        {
            gpio_led.set_low(led_pin_2);
        }
    }

    Zusp::Printf::printf("Terminado.\n");

    return 0;
}
