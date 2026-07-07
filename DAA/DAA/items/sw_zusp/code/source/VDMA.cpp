///    \file VDMA.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    VDMA class implementation.
///


#include <VDMA.h>
#include <Hw_IO.h>


namespace Zusp
{
	/// ************************************************************************************

	///	Writes a value 'register_value' in 'register_addr'
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


	/// ************************************************************************************

	/// Return a specific register address associated to a VDMA channel
	/// \param reg :		Register
	/// \return :			Register \param reg address
	Uint32 VDMA::get_reg_addr(VDMA_register reg)
	{
		Uint32 reg_addr;

		switch(reg)
		{
			case VDMA_cr: 
				reg_addr = base_address + VDMA_mm2s_cr_offs;
				break;
			case VDMA_sr: 
				reg_addr = base_address + VDMA_mm2s_sr_offs;
				break;
			case VDMA_str_addr: 
				reg_addr = base_address + VDMA_mm2s_addr;
				break;
			case VDMA_h_size: 
				reg_addr = base_address + VDMA_mm2s_hs_offs;
				break;
			case VDMA_v_size: 
				reg_addr = base_address + VDMA_mm2s_vs_offs;
				break;
			case VDMA_frm_dly_str: 
				reg_addr = base_address + VDMA_mm2s_st_offs;
				break;
			default:
				reg_addr = 0U;
				break;
		}

		if(direction == VDMA_write && reg_addr != 0U)
		{
			if(reg == VDMA_cr || reg == VDMA_sr)
			{
				reg_addr = reg_addr + VDMA_ch_offs;
			}
			else
			{
				reg_addr = reg_addr + VDMA_ch_B_offs;
			}
		}

		return reg_addr;
	}


	/// Set a quantity of start addresses in VDMA configuration, with its respective
	///	addresses given.
	/// \param start_addr : 	addresses to be set in configuration
	/// \param n_str_addr :		number of addresses to set
	/// \return :				-	0: Everything set
	///							-	1: Error in operation
	Uint8 VDMA::set_start_addr(Uint32* start_addr, Uint8 n_str_addr)
	{
		Uint8 i, res;
		Uint32 str_addr_reg_addr;
		Uint32 nstr_addr_reg_addr;

		if(n_str_addr <= VDMA_frame_buff)
		{
			str_addr_reg_addr = get_reg_addr(VDMA_str_addr);

			for(i = 0; i < n_str_addr; i++)
			{
				nstr_addr_reg_addr = str_addr_reg_addr + (i*VDMA_srt_offs);
				start_address[i] = start_addr[i];
				write_register(nstr_addr_reg_addr, static_cast<Uint32>(start_addr[i]));
			}
			res = 0;
		}		
		else	///	Error in operation
		{
			res = 1;
		}

		return res;
	}


	/// ************************************************************************************

	VDMA::VDMA(	Uint32 base_addr, VDMA_direction dir, Uint32 cr,
        		Uint32* start_addr, Uint32 n_frame, Uint32 size_h, Uint32 size_v)
	{
		base_address = base_addr;
		direction = dir;
		cr_VDMA = cr;
		n_frame_buff = n_frame;
		h_size = size_h;
		v_size = size_v;

		///	Set \param start_address from config
		Uint8 start_addr_ok = set_start_addr(start_addr,n_frame);
	}


	/// ************************************************************************************

	Uint8 VDMA::reset_channel()
	{
		Uint32 cr_reg_addr;
		Uint32 cr_reg;

		cr_reg_addr = get_reg_addr(VDMA_cr);
		cr_reg = read_register(cr_reg_addr);
		write_register(cr_reg_addr, cr_reg | VDMA_reset);	
		
		return 0;
	}


	/// ************************************************************************************

	Uint8 VDMA::config_channel()
	{
		Uint8 result = 0;
		
		Uint32 cr_reg_addr;
		Uint32 vsize_reg_addr;
		Uint32 hsize_reg_addr;
		Uint32 stride_reg_addr;
		Uint32 cr_reg;

		cr_reg_addr = get_reg_addr(VDMA_cr);
		vsize_reg_addr = get_reg_addr(VDMA_v_size);
		hsize_reg_addr = get_reg_addr(VDMA_h_size);
		stride_reg_addr = get_reg_addr(VDMA_frm_dly_str);
		write_register(cr_reg_addr, cr_VDMA);

		cr_reg = read_register(cr_reg_addr);
		cr_reg = (cr_reg & ~(0xFF << VDMA_cnt_offs)) | (n_frame_buff << VDMA_cnt_offs);
		
		write_register(cr_reg_addr, cr_reg);

		if(set_start_addr(start_address, n_frame_buff) != 0)
		{
			result = 1;
		}
		else
		{
			write_register(hsize_reg_addr,static_cast<Uint32>(h_size)*VDMA_px_width);
			write_register(vsize_reg_addr,static_cast<Uint32>(0U));
			write_register(stride_reg_addr,static_cast<Uint32>((h_size)*VDMA_px_width) & 0xFFFFU);
		}

		return result;
	}


	/// ************************************************************************************

	Uint8 VDMA::get_irq(VDMA_irq irq_id)
	{
		Uint8 f_irq = 0;
		Uint32 sr_reg_addr;
		Uint32 sr_reg;

		sr_reg_addr = get_reg_addr(VDMA_sr);


		sr_reg = read_register(sr_reg_addr);
		f_irq = static_cast<Uint8>((sr_reg >> irq_id) & 0x1U);
		
		if(f_irq == 1)
		{
			sr_reg = sr_reg | ((static_cast<Uint32>(1U)) << irq_id); 	//	Clean
			write_register(sr_reg_addr, sr_reg);
		}

		return f_irq;
	}


	/// ************************************************************************************

	Uint8 VDMA::update_frame_addr(Uint32 frame_addr)
	{
		Uint32 str_addr[1] = {frame_addr};
		return set_start_addr(str_addr, static_cast<Uint8>(1U));
	}


	/// ************************************************************************************

	Uint8 VDMA::run_channel()
	{
		Uint32 cr_reg;
		Uint32 cr_reg_addr;
		Uint32 v_size_addr;

		cr_reg_addr = get_reg_addr(VDMA_cr);
		v_size_addr = get_reg_addr(VDMA_v_size);

		cr_reg = read_register(cr_reg_addr);
		cr_reg = cr_reg | VDMA_rs; 											// 	Run
		write_register(cr_reg_addr, cr_reg);
		write_register(v_size_addr,static_cast<Uint32>(v_size)); 			//	LAST STEP, this trigger the transmission

		return 0;
	}
}
