///    \file axi_gpio.h
///
///    \date 21 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    AXI-AXI_GPIO class declaration.
///


#ifndef ZUSP_AXI_GPIO_H_
#define ZUSP_AXI_GPIO_H_

#include <CortexA53/Core_def.h> 

namespace Zusp
{
    /// AXI_GPIO port channel
    enum AXI_GPIO_port
    {
        GPIO_0,
        GPIO_2
    };

    enum AXI_GPIO_err
    {
        err_ok,
        err_size,
        err_pin
    };

    class AXI_GPIO
    {
    public:
        AXI_GPIO(const Uintptr addr, 
                 const Uint8 size_GPIO_0,
                 const Uint8 size_GPIO_2);

        AXI_GPIO_err set_pin(const Uint8 pin, const AXI_GPIO_port port);

        AXI_GPIO_err clear_pin(const Uint8 pin, const AXI_GPIO_port port);

        AXI_GPIO_err set_register(const Uint32 reg, const AXI_GPIO_port port);

        Uint32 get_register(const AXI_GPIO_port port);

    private:
        const Uintptr base_addr;

        const Uint16 sz_GPIO_0;
        const Uint16 sz_GPIO_2;
        
        AXI_GPIO_err check_pin_range(const Uint8 pin, const AXI_GPIO_port port);

        Uint32 get_reg_addr(const AXI_GPIO_port port);

        AXI_GPIO();                                     ///< = delete
        AXI_GPIO(const AXI_GPIO& copy);                 ///< = delete
        AXI_GPIO& operator= (const AXI_GPIO& copy);     ///< = delete
    };
}


#endif 