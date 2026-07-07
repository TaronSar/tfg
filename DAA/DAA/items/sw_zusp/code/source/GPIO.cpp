///    \file GPIO.cpp
///
///    \date 22 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    GPIO class implementation.
///

#include <GPIO.h>
#include <Hw_IO.h>

namespace Zusp
{
    ///	Writes a value 'register_value' in 'register_addr'
    void write_register(Uint32 register_addr, Uint32 register_value)
    {
        Hw_IO::hw_out32(register_addr, register_value);
    }

    /// \param	register_addr 	contains the register to be read from
    /// \return	The value read from the register.
    Uint32 read_register(Uint32 register_addr)
    {
        return Hw_IO::hw_in32(register_addr);
    }

    ///  \param pin_bank:   0-2 (MIO)   ||      3-5 (EMIO)
    GPIO::GPIO(GPIO_bank pin_bank) :
        bank(pin_bank)
    {
        ///  Initialize mode array (default OUTPUT)
        for (int8 i = 0; i < GPIO_max_bits; i++)
        {
            mode_array[i] = GPIO_output;
        }

        ///  Configure bank
        conf_GPIO();
    }


    ///  Configure pin mode and addresses
    void GPIO::conf_GPIO()
    {
        switch (bank)
        {
            case GPIO_bank0:
                write_register((GPIO_baseaddr + GPIO_int_dis0), GPIO_isr_dis);
                mode_addr = GPIO_baseaddr + GPIO_dirm0_offs;
                enable_addr = GPIO_baseaddr + GPIO_oen0_offs;
                input_reg = GPIO_baseaddr + GPIO_d0_ro_offs;
                GPIO_pins = GPIO_min_bits;
                break;
            case GPIO_bank1:
                write_register((GPIO_baseaddr + GPIO_int_dis1), GPIO_isr_dis);
                mode_addr = GPIO_baseaddr + GPIO_dirm1_offs;
                enable_addr = GPIO_baseaddr + GPIO_oen1_offs;
                input_reg = GPIO_baseaddr + GPIO_d1_ro_offs;
                GPIO_pins = GPIO_min_bits;
                break;
            case GPIO_bank2:
                write_register((GPIO_baseaddr + GPIO_int_dis2), GPIO_isr_dis);
                mode_addr = GPIO_baseaddr + GPIO_dirm2_offs;
                enable_addr = GPIO_baseaddr + GPIO_oen2_offs;
                input_reg = GPIO_baseaddr + GPIO_d2_ro_offs;
                GPIO_pins = GPIO_min_bits;
                break;
            case GPIO_bank3:
                write_register((GPIO_baseaddr + GPIO_int_dis3), GPIO_isr_dis);
                mode_addr = GPIO_baseaddr + GPIO_dirm3_offs;
                enable_addr = GPIO_baseaddr + GPIO_oen3_offs;
                input_reg = GPIO_baseaddr + GPIO_d3_ro_offs;
                GPIO_pins = GPIO_max_bits;
                break;
            case GPIO_bank4:
                write_register((GPIO_baseaddr + GPIO_int_dis4), GPIO_isr_dis);
                mode_addr = GPIO_baseaddr + GPIO_dirm4_offs;
                enable_addr = GPIO_baseaddr + GPIO_oen4_offs;
                input_reg = GPIO_baseaddr + GPIO_d4_ro_offs;
                GPIO_pins = GPIO_max_bits;
                break;
            case GPIO_bank5:
                write_register((GPIO_baseaddr + GPIO_int_dis5), GPIO_isr_dis);
                mode_addr = GPIO_baseaddr + GPIO_dirm5_offs;
                enable_addr = GPIO_baseaddr + GPIO_oen5_offs;
                input_reg = GPIO_baseaddr + GPIO_d5_ro_offs;
                GPIO_pins = GPIO_max_bits;
                break;
        }

    }


    ///  \param mode: mode to set the pin (INPUT/OUTPUT)
    ///  Set pin value
    void GPIO::config_pin(Uint8 pin, GPIO_mode mode)
    {
        Uint32 mode_value = read_register(mode_addr);
        Uint32 enable_value = read_register(enable_addr);

        if (mode == GPIO_input)
        {
            mode_value &= ~(1U << pin);
            enable_value &= ~(1U << pin);

            write_register(mode_addr, mode_value);
            write_register(enable_addr, enable_value);
        }
        else
        {
            mode_value |= (1U << pin);
            enable_value |= (1U << pin);

            write_register(mode_addr, mode_value);
            write_register(enable_addr, enable_value);
        }

        ///  Store pin mode
        mode_array[pin] = mode;
    }

    ///  Set value to determined pin
    void GPIO::set_pin(Uint8 pin, GPIO_value val)
    {
        Uint32 output_reg;                              ///  Write/change pin value
        Uint8 pin_value = pin;

        /// Pin value change for setting
        /// -   LSW:    DATA goes from 0:15
        /// -   MSW:    DATA goes from 0:9 (MIO) / 0:15 (EMIO)
        /// \param pin_value is used to set the pin value below
        if (pin >= GPIO_bits_low)
        {
            pin_value = pin - GPIO_bits_low;
        }


        switch (bank)
        {
            case GPIO_bank0:
                if (pin < GPIO_bits_low)
                {
                    output_reg = GPIO_baseaddr + GPIO_data0_LSW;
                }
                else
                {
                    output_reg = GPIO_baseaddr + GPIO_data0_MSW;
                }
                break;
            case GPIO_bank1:
                if (pin < GPIO_bits_low)
                {
                    output_reg = GPIO_baseaddr + GPIO_data1_LSW;
                }
                else
                {
                    output_reg = GPIO_baseaddr + GPIO_data1_MSW;
                }
                break;
            case GPIO_bank2:
                if (pin < GPIO_bits_low)
                {
                    output_reg = GPIO_baseaddr + GPIO_data2_LSW;
                }
                else
                {
                    output_reg = GPIO_baseaddr + GPIO_data2_MSW;
                }
                break;
            case GPIO_bank3:
                if (pin < GPIO_bits_low)
                {
                    output_reg = GPIO_baseaddr + GPIO_data3_LSW;
                }
                else
                {
                    output_reg = GPIO_baseaddr + GPIO_data3_MSW;
                }
                break;
            case GPIO_bank4:
                if (pin < GPIO_bits_low)
                {
                    output_reg = GPIO_baseaddr + GPIO_data4_LSW;
                }
                else
                {
                    output_reg = GPIO_baseaddr + GPIO_data4_MSW;
                }
                break;
            case GPIO_bank5:
                if (pin < GPIO_bits_low)
                {
                    output_reg = GPIO_baseaddr + GPIO_data5_LSW;
                }
                else
                {
                    output_reg = GPIO_baseaddr + GPIO_data5_MSW;
                }
                break;
        }


        ///  Set pin mask value
        Uint32 out_value = read_register(output_reg);
        if (mode_array[pin] == GPIO_input)
        {
            out_value |= (1U << (pin_value + GPIO_bits_low));
            write_register(output_reg, out_value);
        }
        else    ///  Pin can change value
        {
            out_value &= ~(1U << (pin_value + GPIO_bits_low));
            write_register(output_reg, out_value);
        }


        if (val == GPIO_low)
        {
            out_value &= ~(1U << pin_value);
            write_register(output_reg, out_value);
        }
        else
        {
            out_value |= (1U << pin_value);
            write_register(output_reg, out_value);
        }

    }

    ///  Get GPIO value (from RO data)
    GPIO_value GPIO::get_val(Uint8 pin)
    {
        GPIO_value pin_value;
        Uint32 in_value = read_register(input_reg);

        ///  Mask pin value (see 1st pin value)
        bool bit_value = (in_value >> pin) & 0x1;
        pin_value = bit_value ? GPIO_high : GPIO_low;

        return pin_value;
    }

    ///  Get bank that contains the pin
    GPIO_bank GPIO::get_bank()
    {
        return bank;
    }

    /// \param val:         Value to set the GPIO pin. Can be:
    ///                     -   GPIO_high
    ///                     -   GPIO_low
    void GPIO::set_val(Uint8 pin, GPIO_value val)
    {
        set_pin(pin, val);
    }

    /// Set GPIO pin to LOW value
    void GPIO::set_low(Uint8 pin)
    {
        set_pin(pin, GPIO_low);
    }

    /// Set GPIO pin to HIGH value
    void GPIO::set_high(Uint8 pin)
    {
        set_pin(pin, GPIO_high);
    }

    /// Change GPIO pin value:
    /// If \param pin is HIGH, change to LOW
    /// If \param pin is LOW, change to HIGH
    void GPIO::toggle(Uint8 pin)
    {
        /// Get GPIO value
        GPIO_value val = get_val(pin);

        if (val == GPIO_high)
        {
            set_low(pin);
        }
        else
        {
            set_high(pin);
        }
    }
}