///    \file DMA_channel.h
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    DMA_channel class declaration.
///


#ifndef ZUSP_DMA_H_
#define ZUSP_DMA_H_

#include <Entypes.h>
#include <Parameters.h>
#include <CortexA53/Core_def.h>

namespace Zusp
{
    /// DMA_channel direction set
    enum DMA_direction_t
    {
        write,      /// s2mm (Stream to Memory): Transfer data from the stream interface to memory
        read        /// mm2s (Memory to Stream): Transfer data from memory to the stream interface
    };

    /// DMA_channel register options
    enum DMA_register_t
    {
        DMA_dmacr, 
        DMA_dmasr, 
        DMA_taddr,
        DMA_taddr_msb, 
        DMA_length    
    };

    /// DMA_channel interrupts used
    enum DMA_irq_t
    {
        DMA_irq_int_err = 4U,
        DMA_irq_slv_err = 5U,
        DMA_irq_dec_err = 6U,
        DMA_irq_sg_int_err = 8U,
        DMA_irq_sg_slv_err = 9U,
        DMA_irq_sf_dec_err = 10U,
        DMA_irq_ioc = 12U,  
        DMA_irq_dly = 13U,
        DMA_irq_err = 14U
    };

    class DMA
    {
    public: 
        class DMA_channel
        {
        public:
            DMA_channel(const Uintptr base_addr,
                        const Uintptr target_addr,
                        const Uint32 len,
                        const Uint16 offs);

            Uint8 reset_core();

            Uint8 config_channel();

            Uint8 get_irq(const DMA_irq_t irq_id);

            Uint8 run_channel();

            Uint8 stop_channel();

            Uint8 wait_idle();

            Uint32 get_length();

            void change_target(const Uint32 addr);

        private:
            Uintptr base_address;
            Uintptr target_address;     ///< destination or source
            Uint32 length;
            Uint32 irqs;
            Uint16 offset;              ///< Base addres offset for each chanel

            Uint32 get_reg_addr(const DMA_register_t reg);

            DMA_channel();                              ///< = delete
            DMA_channel(const DMA_channel& copy);               ///< = delete
            DMA_channel& operator= (const DMA_channel& copy);   ///< = delete
        };

        DMA(const Uintptr base_addr);

        void create(const DMA_direction_t dir, 
                    const Uintptr target_addr,
                    const Uint32 len);

        DMA_channel* write_channel;
        DMA_channel* read_channel;
    private:
        Uintptr base_address;
    };

}


#endif