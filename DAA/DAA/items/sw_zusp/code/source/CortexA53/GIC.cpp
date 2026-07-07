///    \file GIC.cpp
///
///    \date 29 ago. 2024
///
///    \author      Victor Morales, vmm6 (at) embention.com
///    Company      Embention S.A.
///
///    GIC class implementation.
///

#include <GIC.h>
#include <Hw_IO.h>
#include <Parameters.h>

namespace Zusp
{
    /// Write Byte.
    /// \param[in] base_address         Base address of byte to be written.
    /// \param[in] register_value       Value to be set at byte.
    /// \return none.
    void write_byte(Uint32 base_address, Uint8 register_value)
    {
    	Hw_IO::hw_out8(static_cast<Uintptr>(base_address), (register_value));
    }

    /// Read Byte.
    /// \param[in] base_address         Base address of byte to be read.
    /// \return Value of the byte.
    Uint8 read_byte(Uint32 base_address)
    {
        Uint8 ret_value;
    	ret_value = Hw_IO::hw_in8(static_cast<Uintptr>(base_address));
        return ret_value;
    }

    /// Write register.
    /// \param[in] base_address         Base address of register to be written.
    /// \param[in] register_value       Value to be set at register.
    /// \return none.
    void write_register(Uint32 base_address, Uint32 register_value)
    {
    	Hw_IO::hw_out32(static_cast<Uintptr>(base_address), (register_value));
    }

    /// Read register.
    /// \param[in] base_address         Base address of register to be read.
    /// \return Value of the register.
    Uint32 read_register(Uint32 base_address)
    {
        Uint32 ret_value;
    	ret_value = Hw_IO::hw_in32(static_cast<Uintptr>(base_address));
        return ret_value;
    }
    
    /// Write distributor register.
    /// \param[in] register_offs        Offset of the register to be set.
    /// \param[in] register_value       Value to be set at register.
    /// \return none.
    void write_distr(Uint32 register_offs, Uint32 register_value)
    {
    	write_register(GIC_base_addr + GICD_offs + register_offs, register_value);
    }
    
    /// Read distributor register.
    /// \param[in] register_offs         Offset of the register to be read.
    /// \return Value of the register.
    Uint32 read_distr(Uint32 register_offs)
    {
        Uint32 ret_value;
    	ret_value = read_register(GIC_base_addr + GICD_offs + register_offs);
        return ret_value;
    }
    
    /// Write interface register.
    /// \param[in] register_offs        Offset of the register to be set.
    /// \param[in] register_value       Value to be set at register.
    /// \return none.
    void write_interface(Uint32 register_offs, Uint32 register_value)
    {
    	write_register(GIC_base_addr + GICC_offs + register_offs, register_value);
    }
    
    /// Read interface register.
    /// \param[in] register_offs         Offset of the register to be read.
    /// \return Value of the register.
    Uint32 read_interface(Uint32 register_offs)
    {
        Uint32 ret_value;
    	ret_value = read_register(GIC_base_addr + GICC_offs + register_offs);
        return ret_value;
    }
    
    /// Configure setting/clearing interrupt.
    /// \param[in] offset         Offset of the configuration register.
    /// \param[in] intr_id        Interrupt identification.
    /// \return none.
    void interrupt_conf(Uint32 offset, Uint16 intr_id)
    {
        Uint32 intr_bit = 0;
        Uint8 bit_offs = 0;

        // Obtain the bit offset in the register to shift the bit mask
        bit_offs = intr_id - ((intr_id/GICD_reg_size)*GICD_reg_size);
        intr_bit = 1 << bit_offs;
        
        // Write '1' at the register bit
        write_distr(offset + (intr_id/GICD_reg_size), intr_bit);

    }


    
    /// Distributor initialization.
    /// \return none.
    void GIC::init_distr()
    {
        Uint16 it_lines_number;
        Uint16 iter;

        it_lines_number = GIC_n_irqs;

        //Disable distributor
        write_distr(GICD_ctrl_offs, 0);

        //Configure SPIs every to level-sensitive and active high
	    for (iter = GIC_spi_idx; iter < it_lines_number; iter += GICD_icfg_n_int)
        {
            write_distr(GICD_icfg_offs + ((iter * register_bytes) / GICD_icfg_n_int), 0UL);
	    }
 
        // Set default priority for every interruption
	    for (iter = GIC_sgi_idx; iter < it_lines_number; iter++)
        {
            set_intr_prior(iter, GIC_def_prior); 
	    }

        // Set default target for SPI interruption
	    for (iter = GIC_spi_idx; iter < it_lines_number; iter+=GICD_reg_size)
        {
            add_target(iter, 1UL);
	    }
    
        // Disable every interruption
	    for (iter = GIC_sgi_idx; iter < it_lines_number; iter+=GICD_reg_size)
        {
            write_distr(GICD_icen_offs + ((iter * register_bytes)/ GICD_reg_size), GIC_clr_reg);
	    }
         
        //Enable distributor
        write_distr(GICD_ctrl_offs, 1U);

    }
    
    /// CPU interface initialization.
    /// \return none.
    void GIC::init_interface()
    {
        // Default configuration, EOIR with deactivation funcitonality, IRQ and FIQ Bypass, disable signaling group1
        write_interface(GICC_ctlr_offs, 0x00);

        // Set CPU interface priority to max value
        write_interface(GICC_pmr_offs, GIC_max_prior);

        // To default value, secure copy
        write_interface(GICC_bpr_offs, GICC_bpr_secure);

        // Basic enablement for cpu interface
        write_interface(GICC_ctlr_offs, 0x01);
    }
       
    /// Interrupt enabling.
    /// \param[in] intr_id        Interrupt identification.
    /// \return none.
    void GIC::enable(Uint16 intr_id)
    {
        interrupt_conf(GICD_isen_offs, intr_id);
    }
    
    /// Interrupt disabling.
    /// \param[in] intr_id        Interrupt identification.
    /// \return none.
    void GIC::disable(Uint16 intr_id)
    {   
        interrupt_conf(GICD_icen_offs, intr_id);
    }
 
    /// Interrupt setting pending.
    /// \param[in] intr_id        Interrupt identification.
    /// \return none.
    void GIC::set_pending(Uint16 intr_id)
    {
        interrupt_conf(GICD_ispen_offs, intr_id);
    }
 
    /// Interrupt clearing pending.
    /// \param[in] intr_id        Interrupt identification.
    /// \return none.
    void GIC::clr_pending(Uint16 intr_id)
    {
        interrupt_conf(GICD_icpen_offs, intr_id);
    }

    /// Interrupt setting active.
    /// \param[in] intr_id        Interrupt identification.
    /// \return none.
    void GIC::set_active(Uint16 intr_id)
    {
        interrupt_conf(GICD_isact_offs, intr_id);
    }

    /// Interrupt clearing active.
    /// \param[in] intr_id        Interrupt identification.
    /// \return none.
    void GIC::clr_active(Uint16 intr_id)
    {
        interrupt_conf(GICD_icact_offs, intr_id);
    }

    /// Interrupt group assignation.
    /// \param[in] intr_id         Interrupt identification.
    /// \param[in] group           group identification.
    /// \return none.
    void GIC::assign_group(Uint16 intr_id, Interrupt_group group)
    {

        Uint32 intr_bit = 0;
        Uint8 bit_offs = 0;
        Uint32 GICD_igrpn_val = 0;
        Uint32 GICD_igrpn_addr = 0;

        // Obtain the bit offset in the register to shift the bit mask
        bit_offs = intr_id - ((intr_id/GICD_reg_size)*GICD_reg_size);
        intr_bit = 1 << bit_offs;
        
        // Obtain the register address 
        GICD_igrpn_addr = GICD_igrpn_offs + (intr_id/GICD_reg_size);

        // Get the current value of the group register
        GICD_igrpn_val = read_distr(GICD_igrpn_addr);

        // Depending the group to set
        if(group == group_0)
        {
            GICD_igrpn_val = GICD_igrpn_val & ~(intr_bit);
        }
        else 
        {
            GICD_igrpn_val = GICD_igrpn_val | intr_bit;
        }    


        // Write '1' at the register bit
        write_distr(GICD_igrpn_addr, GICD_igrpn_val);

        
    }

    /// Group enabling.
    /// \param[in] group           group identification.
    /// \return none.
    void GIC::enable_group(Interrupt_group group)
    {
        Uint32 GICD_ctrl_val;

        GICD_ctrl_val = read_distr(GICD_ctrl_offs);

        if(group == group_0)
        {
            GICD_ctrl_val = GICD_ctrl_val | (GICD_ctlr_grp0);
        }
        else 
        {
            GICD_ctrl_val = GICD_ctrl_val | (GICD_ctlr_grp1);
        }        

        write_distr(GICD_ctrl_offs, GICD_ctrl_val);
    }

    /// Group disabling.
    /// \param[in] group           group identification.
    /// \return none.
    void GIC::disable_group(Interrupt_group group)
    {
        Uint32 GICD_ctrl_val;

        GICD_ctrl_val = read_distr(GICD_ctrl_offs);

        if(group == group_0)
        {
            GICD_ctrl_val = GICD_ctrl_val & ~(GICD_ctlr_grp0);
        }
        else 
        {
            GICD_ctrl_val = GICD_ctrl_val & ~(GICD_ctlr_grp1);
        }
    }

    /// Interrupt targeting to specific CPU core.
    /// \param[in] intr_id         Interrupt identification.
    /// \param[in] target          Cpu target.
    /// \return none.
    void GIC::add_target(Uint16 intr_id, Uint8 target)
    {
        Uint8 core_targets;
        Uint8 GICD_itargn_val;
        Uint32 GICD_itargn_addr;

        core_targets = 1U < target;

        GICD_itargn_addr = GIC_base_addr + GICD_offs + GICD_itarg_offs + intr_id;

        GICD_itargn_val = read_byte(GICD_itargn_addr);

        GICD_itargn_val = GICD_itargn_val | core_targets;

        write_byte(GICD_itargn_addr, GICD_itargn_val);
    }

    /// Remove interrupt targeting to specific CPU core.
    /// \param[in] intr_id         Interrupt identification.
    /// \param[in] target          Cpu target.
    /// \return none.
    void GIC::remove_target(Uint16 intr_id, Uint8 target)
    {
        Uint8 core_targets;
        Uint8 GICD_itargn_val;
        Uint32 GICD_itargn_addr;

        core_targets = 1U < target;

        GICD_itargn_addr = GIC_base_addr + GICD_offs + GICD_itarg_offs + intr_id;

        GICD_itargn_val = read_byte(GICD_itargn_addr);

        GICD_itargn_val = GICD_itargn_val & ~core_targets;

        write_byte(GICD_itargn_addr, GICD_itargn_val);
    }

    /// Interrupt targeting to multiple CPU core.
    /// \param[in] intr_id         Interrupt identification.
    /// \param[in] target          Cpu targets.
    /// \return none.
    void GIC::set_targets(Uint16 intr_id, Uint8 targets)
    {
        write_byte(GIC_base_addr + GICD_offs + GICD_itarg_offs + intr_id, targets);
    }

    /// Configure assertion and model of interrupt.
    /// \param[in] intr_id         Interrupt identification.
    /// \param[in] assert          Interrupt assert.
    /// \param[in] model           Interrupt model.
    /// \return none.
    void GIC::set_config(Uint16 intr_id, Interrupt_assert assert, Interrupt_model model)
    {

        Uint32 intr_bit = 0;
        Uint8 bit_offs = 0;
        Uint32 GICD_icfgn_val = 0;
        Uint32 GICD_icfgn_addr = 0;

        // Obtain the bit offset in the register to shift the bit mask
        bit_offs = (intr_id - ((intr_id/GICD_icfg_n_int)*GICD_icfg_n_int)) * GICD_icfg_int_b;
        intr_bit = 1 << bit_offs;
        
        GICD_icfgn_addr = GICD_icfg_offs + (intr_id/GICD_icfg_n_int); 

        GICD_icfgn_val = read_distr(GICD_icfgn_addr);

        if(assert == level_sen)
        {
            GICD_icfgn_val = GICD_icfgn_val & ~(intr_bit);
        }
        else 
        {
            GICD_icfgn_val = GICD_icfgn_val | intr_bit;
        }    


        if(model == N_N)
        {
            GICD_icfgn_val = GICD_icfgn_val & ~(intr_bit << 1U);
        }
        else 
        {
            GICD_icfgn_val = GICD_icfgn_val | (intr_bit << 1U);
        }    

        // Write '1' at the register bit
        write_distr(GICD_icfgn_addr, GICD_icfgn_val);
    }
    
    /// Trigger secure sgi to specific target.
    /// \param[in] intr_id          Interrupt identification.
    /// \param[in] cpu_target_list  Cpu core target.
    /// \return none.
    void GIC::trigg_sec_sgi(Uint16 intr_id, Uint8 cpu_target_list)
    {
        Uint32 sgir;

        if(intr_id < GIC_n_sgi){
            sgir = (intr_id) & 0x0F;
            sgir |= (static_cast<Uint32>(cpu_target_list & 0xFF) << 16);
            sgir |= GICD_sgi_list;
            
            write_distr(GICD_sgi_offs, sgir);
        }
    }
    
    /// Trigger non-secure sgi to specific target.
    /// \param[in] intr_id          Interrupt identification.
    /// \param[in] cpu_target_list  Cpu core target.
    /// \return none.
    void GIC::trigg_nsec_sgi(Uint16 intr_id, Uint8 cpu_target_list)
    {
        Uint32 sgir;

        if(intr_id < GIC_n_sgi){
            sgir = (intr_id) & 0x0F;
            sgir |= (static_cast<Uint32>(cpu_target_list & 0xFF) << 16);
            sgir |= GICD_sgi_list;
            sgir |= GICD_sgi_nsatt;
            
            write_distr(GICD_sgi_offs, sgir);
        }
    }
    
    /// Set SGI as pending.
    /// \param[in] intr_id          Interrupt identification.
    /// \param[in] cpu_target_list  Cpu core target.
    /// \return none.
    void GIC::set_pend_sgi(Uint16 intr_id, Uint8 cpu_target_list)
    {
        Uint32 sgir;
        Uint8 register_offs;
        Uint8 bits_offs;

        if(intr_id < GIC_n_sgi){
            register_offs = intr_id >> 2;
            bits_offs = intr_id & 0x03; 
            sgir = read_distr(GICD_sgi_s_offs + register_offs);
            sgir |= cpu_target_list << bits_offs;
            write_distr(GICD_sgi_s_offs + register_offs, sgir);
        }
    }
    
    /// Clear pending SGI.
    /// \param[in] intr_id          Interrupt identification.
    /// \param[in] cpu_target_list  Cpu core target.
    /// \return none.
    void GIC::clr_pend_sgi(Uint16 intr_id, Uint8 cpu_target_list)
    {
        Uint32 sgir;
        Uint8 register_offs;
        Uint8 bits_offs;

        if(intr_id < GIC_n_sgi){
            register_offs = intr_id >> 2;
            bits_offs = intr_id & 0x03; 
            sgir = read_distr(GICD_sgi_s_offs + register_offs);
            sgir |= (cpu_target_list << bits_offs);
            write_distr(GICD_sgi_s_offs + register_offs, sgir);
        }
    }
    
    /// Set cpu interface priority.
    /// \param[in] priority          Priority level.
    /// \return none.
    void GIC::set_iface_prior(Uint8 priority)
    {
        // Set CPU interface priority to max value
        write_interface(GICC_pmr_offs, priority);
    }

    /// Set interrupt priority.
    /// \param[in] priority          Priority level.
    /// \return none.
    void GIC::set_intr_prior(Uint16 intr_id, Uint8 priority)
    {
        // Set priority for interrupt
        write_byte(GIC_base_addr + GICD_offs + GICD_iprio_offs + intr_id, priority);
    }

    /// Get signaled irq.
    /// \return signaled irq id.
    Uint16 GIC::get_signald_irq()
    {
        Uint32 iar_reg_val;
        Uint16 irq_id;

        iar_reg_val = read_interface(GICC_iar_offs);

        iar_reg_val &= GICC_iar_irq_id;

        irq_id = static_cast<Uint16>(iar_reg_val);

        return irq_id;
    }

}