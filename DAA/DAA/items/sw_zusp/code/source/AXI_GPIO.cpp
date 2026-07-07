///    \file axi_gpio.cpp
///
///    \date 21 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    AXI-GPIO class implementation.
///


#include <AXI_GPIO.h>
#include <Parameters.h>
#include <Hw_IO.h>

namespace Zusp
{
    //	Writes a value 'register_value' in 'register_addr'
    void write_register(Uint32 register_addr,Uint32 register_value)
    {
        Hw_IO::hw_out32(register_addr, register_value);
    }

    /// \param	register_addr 	contains the register to be read from
	/// \return	The value read from the register.
	Uint32 read_register(Uint32 register_addr)
	{
		return Hw_IO::hw_in32(register_addr);
	}

    AXI_GPIO_err AXI_GPIO::check_pin_range(const Uint8 pin, const AXI_GPIO_port port)
    {
        AXI_GPIO_err ret = err_ok;

        if(port == GPIO_0 && (pin >= sz_GPIO_0 || pin < min_pin_range) ||
           port == GPIO_2 && (pin >= sz_GPIO_2 || pin < min_pin_range))
        {
            ret = err_pin;
        }

        if((sz_GPIO_0 > max_pin_range || sz_GPIO_0 < min_pin_range) ||
           (sz_GPIO_2 > max_pin_range || sz_GPIO_2 < min_pin_range))
        {
            ret = err_size;
        }

        return ret;
    }

    Uint32 AXI_GPIO::get_reg_addr(const AXI_GPIO_port port)
    {
        return (port == GPIO_0) ? base_addr + AXI_GPIO0_offs : base_addr + AXI_GPIO1_offs;
    }

    // Size < 32
    AXI_GPIO::AXI_GPIO(const Uintptr addr, 
                       const Uint8 size_GPIO_0,
                       const Uint8 size_GPIO_2) :
        base_addr(addr),
        sz_GPIO_0(size_GPIO_0),
        sz_GPIO_2(size_GPIO_2)
    {
    }

    AXI_GPIO_err AXI_GPIO::set_pin(const Uint8 pin, const AXI_GPIO_port port)
    {
        AXI_GPIO_err ret = check_pin_range(pin, port);

        Uint32 reg_addr = get_reg_addr(port);

        //  Register update (set bit)
        if(ret == err_ok)
        {
            Uint32 data_register = read_register(reg_addr);
            data_register = data_register | (static_cast<Uint32>(1U) << pin);
            write_register(reg_addr, data_register);
        }

        return ret;
    }

    AXI_GPIO_err AXI_GPIO::clear_pin(const Uint8 pin, const AXI_GPIO_port port)
    {
        AXI_GPIO_err ret = check_pin_range(pin, port);

        Uint32 reg_addr = get_reg_addr(port);

        // Register update (clear bit)
        if(ret == err_ok)
        {
            Uint32 data_register = read_register(reg_addr);
            data_register = data_register & ~(static_cast<Uint32>(1U) << pin);
            write_register(reg_addr, data_register);
        }

        return ret;
    }
    
    AXI_GPIO_err AXI_GPIO::set_register(const Uint32 reg, const AXI_GPIO_port port)
    {
        AXI_GPIO_err ret = err_ok;

        Uint32 reg_addr = get_reg_addr(port);

        write_register(reg_addr, reg);

        return ret;
    }
    
    Uint32 AXI_GPIO::get_register(const AXI_GPIO_port port)
    {
        Uint32 reg_addr = get_reg_addr(port);

        return read_register(reg_addr);
    }
}