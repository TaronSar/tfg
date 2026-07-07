///    \file DMA_channel.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    DMA_channel class implementation.
///


#include <DMA.h>
#include <Hw_IO.h>
#include <Sleep.h>


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


    static void wait_reg_bits(Uint32 addr, 
                              Uint32 bit_mask, 
                              Uint32 tries)
    {
        Uint32 val;
        Uint32 try_val;
        Uint32 real_tries;

        if (tries == 0)
        { 	///Infinitive wait
            try_val = 0;
            real_tries = 1;
        }

        do
        {
            val = read_register(addr);
            if (tries != 0)
            {
                try_val++;
            }
        } while (((val & bit_mask) == 0) && (try_val <= real_tries));
    }

    DMA::DMA_channel::DMA_channel(const Uintptr base_addr,
                                  const Uintptr target_addr,
                                  const Uint32 len,
                                  const Uint16 offs) :
        base_address(base_addr),
        target_address(target_addr),
        length(len),
        offset(offs)
    {
        reset_core();
        config_channel();
    }

    Uint32 DMA::DMA_channel::get_reg_addr(const DMA_register_t reg)
    {
        Uint32 reg_addr;
        Uint32 b_addr = base_address;

        switch (reg)
        {
            case DMA_dmacr:
                reg_addr = b_addr + DMA_m2s_cr_offs;
                break;
            case DMA_dmasr:
                reg_addr = b_addr + DMA_m2s_sr_offs;
                break;
            case DMA_taddr:
                reg_addr = b_addr + DMA_m2s_SA_offs;
                break;
            case DMA_taddr_msb:
                reg_addr = b_addr + DMA_m2s_SM_offs;
                break;
            case DMA_length:
                reg_addr = b_addr + DMA_m2s_l_offs;
                break;
            default:
                reg_addr = 0U;
                break;
        }

        reg_addr = reg_addr + offset;

        return reg_addr;
    }

    ///	Change DMA_channel target address
    void DMA::DMA_channel::change_target(const Uint32 addr)
    {
        target_address = addr;

        Uint32 target_addr_reg_addr = get_reg_addr(DMA_taddr);
        Uint32 target_addr_msb_reg_addr = get_reg_addr(DMA_taddr_msb);

        write_register(target_addr_reg_addr, static_cast<Uint32>(addr & DMA_sr_value));
        write_register(target_addr_msb_reg_addr, static_cast<Uint32>((addr >> max_pin_range) & DMA_sr_value));
    }


    Uint8 DMA::DMA_channel::reset_core()
    {
        Uint32 DMA_reg_addr;
        Uint32 DMA_reg;

        DMA_reg_addr = get_reg_addr(DMA_dmacr);

        DMA_reg = read_register(DMA_reg_addr);
        write_register(DMA_reg_addr, DMA_reg | DMA_cr_reset);

        Zusp::Sleep::sleep_us(rst_time);
        return 0;
    }


    Uint8 DMA::DMA_channel::config_channel()
    {
        Uint32 DMA_reg_addr = get_reg_addr(DMA_dmacr);


        ///Configure Irqs enabled
        write_register(DMA_reg_addr, irqs);

        ///	Set target in HW
        change_target(target_address);

        return 0;
    }


    Uint8 DMA::DMA_channel::get_irq(const DMA_irq_t irq_id)
    {
        Uint8 f_irq = 0;
        Uint32 DMA_sr_reg_addr;
        Uint32 DMA_sr_reg;
        Uint32 irq_value = static_cast<Uint32>(irq_id);

        DMA_sr_reg_addr = get_reg_addr(DMA_dmasr);

        DMA_sr_reg = read_register(DMA_sr_reg_addr);

        f_irq = static_cast<Uint8>((DMA_sr_reg >> irq_value) & 0x1U);
        if (f_irq == 1)
        {
            DMA_sr_reg = DMA_sr_reg | ((static_cast<Uint32>(1U)) << irq_value);
            write_register(DMA_sr_reg_addr, DMA_sr_reg);
        }
        return f_irq;
    }


    Uint32 DMA::DMA_channel::get_length()
    {
        Uint32 DMA_sr_reg_addr;
        Uint32 DMA_sr_reg;

        DMA_sr_reg_addr = get_reg_addr(DMA_length);

        DMA_sr_reg = read_register(DMA_sr_reg_addr);

        return DMA_sr_reg;
    }


    Uint8 DMA::DMA_channel::run_channel()
    {
        Uint32 lenght_reg_addr;
        Uint32 DMA_reg_addr;
        Uint32 DMA_reg;

        DMA_reg_addr = get_reg_addr(DMA_dmacr);
        lenght_reg_addr = get_reg_addr(DMA_length);

        DMA_reg = read_register(DMA_reg_addr);
        write_register(DMA_reg_addr, DMA_reg | DMA_cr_rs);
        write_register(lenght_reg_addr, length);

        return 0;
    }


    Uint8 DMA::DMA_channel::stop_channel()
    {
        Uint32 DMA_reg_addr;
        Uint32 DMA_sr_reg_addr;
        Uint32 DMA_reg;

        DMA_reg_addr = get_reg_addr(DMA_dmacr);
        DMA_sr_reg_addr = get_reg_addr(DMA_dmasr);

        DMA_reg = read_register(DMA_reg_addr);
        write_register(DMA_reg_addr, DMA_reg & ~(static_cast<Uint32>(DMA_cr_rs)));

        wait_reg_bits(DMA_sr_reg_addr, DMA_sr_halt, DMA_wait_tries);

        return 0;
    }


    Uint8 DMA::DMA_channel::wait_idle()
    {
        Uint32 DMA_sr_reg_addr;

        DMA_sr_reg_addr = get_reg_addr(DMA_dmasr);

        wait_reg_bits(DMA_sr_reg_addr, DMA_sr_idle, DMA_wait_tries);

        return 0;
    }

    Zusp::DMA::DMA(const Uintptr base_addr) :
        base_address(base_addr),
        write_channel(0),
        read_channel(0)
    {
    }

    void DMA::create(const DMA_direction_t dir, 
                     const Uintptr target_addr,
                     const Uint32 len)
    {
        if(write_channel == 0 && dir == write)
        {
            write_channel = new DMA_channel(base_address, 
                                           target_addr,
                                           len,
                                           DMA_ch_offs);
        }
        if(read_channel == 0 && dir == read)
        {
            read_channel = new DMA_channel(base_address, 
                                           target_addr,
                                           len,
                                           0);
        }
    }

}