///    \file GPIO.h
///
///    \date 22 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    GPIO class declaration.
///    


#ifndef ZUSP_GPIO_H_
#define ZUSP_GPIO_H_

#include <Parameters.h>

namespace Zusp
{
    ///  GPIO mode for each pin configured
    enum GPIO_mode
    {
        GPIO_input,
        GPIO_output
    };

    ///  GPIO value for each pin
    enum GPIO_value
    {
        GPIO_low,
        GPIO_high
    };

    ///  GPIO pin banks avaliable (MIO and EMIO)
    enum GPIO_bank
    {
        GPIO_bank0, GPIO_bank1,
        GPIO_bank2, GPIO_bank3,
        GPIO_bank4, GPIO_bank5
    };

    ///  Simulates the configuration of a pin contained in GPIO
    class GPIO
    {
    public:
        GPIO(GPIO_bank pin_bank);

        GPIO_value get_val(Uint8 pin);                  ///  Return GPIO value

        GPIO_bank get_bank();

        void config_pin(Uint8 pin, GPIO_mode mode);

        void set_val(Uint8 pin, GPIO_value val);        ///  Set pin from bank to value 'val'

        void set_low(Uint8 pin);                        ///  Set GPIO pin to low

        void set_high(Uint8 pin);                       ///  Set GPIO pin to high

        void toggle(Uint8 pin);                         ///  Toggle GPIO pin value

    private:
        GPIO_bank bank;
        Uint8 GPIO_pins;                                ///  Quantity of pins in bank
        Uint32 input_reg;                               ///  Read pin value (read-only)
        Uint32 mode_addr;
        Uint32 enable_addr;
        GPIO_mode mode_array[GPIO_max_bits];

        void conf_GPIO();

        void set_pin(Uint8 pin, GPIO_value val);        ///  Set pin value

        GPIO();                                 ///< = delete
        GPIO(const GPIO& copy);                 ///< = delete
        GPIO& operator= (const GPIO& copy);     ///< = delete
    };
}

#endif