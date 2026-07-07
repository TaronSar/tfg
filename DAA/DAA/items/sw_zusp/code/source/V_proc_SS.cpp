///    \file Printf.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Printf class implementation.
///


#include <V_proc_SS.h>
#include <Hw_IO.h>


namespace Zusp
{
	///	*****************************************************************************

	///	Writes a value 'register_value' in 'register_addr'
    void write_register(Uint32 register_addr,Uint32 register_value)
    {
        Hw_IO::hw_out32(register_addr, register_value);
    }


	///	*****************************************************************************
	///	Default constructor
	V_proc_SS::V_proc_SS(Uint32 addr, Uint32 proc_width,
                        Uint32 proc_height, Uint32 proc_data_width)
	{
		base_address = addr;
		width = proc_width;
		height = proc_height;
		data_width = proc_data_width;
	}


	///	*****************************************************************************
	///	Setup of V_Proc_SS
	Uint8 V_proc_SS::setup()
	{
		/// Set coef scalar factor 4096
		/// Set offset scalar factor 256
		/// Set coeff values depending ranges
		
		/// NO COLOR TRANSFORMATION
		write_register(base_address + VPSS_K11_offs, static_cast<int32>(VPSS_K11_factor*static_cast<float>(VPSS_scale_coef)));	//red
		write_register(base_address + VPSS_K12_offs, static_cast<int32>(VPSS_K12_factor*static_cast<float>(VPSS_scale_coef)));
		write_register(base_address + VPSS_K13_offs, static_cast<int32>(VPSS_K13_factor*static_cast<float>(VPSS_scale_coef)));

		write_register(base_address + VPSS_K21_offs, static_cast<int32>(0*static_cast<float>(VPSS_scale_coef)));
		write_register(base_address + VPSS_K22_offs, static_cast<int32>(0*static_cast<float>(VPSS_scale_coef)));	//green
		write_register(base_address + VPSS_K23_offs, static_cast<int32>(0*static_cast<float>(VPSS_scale_coef)));

		write_register(base_address + VPSS_K31_offs, static_cast<int32>(0*static_cast<float>(VPSS_scale_coef)));
		write_register(base_address + VPSS_K32_offs, static_cast<int32>(0*static_cast<float>(VPSS_scale_coef)));
		write_register(base_address + VPSS_K33_offs, static_cast<int32>(0*static_cast<float>(VPSS_scale_coef)));	//blue
		write_register(base_address + VPSS_R_offs, (0));
		write_register(base_address + VPSS_G_offs, (0));
		write_register(base_address + VPSS_B_offs, (0));
		
		write_register(base_address + VPSS_in_offs, 0U); 			/// RGB
		write_register(base_address + VPSS_out_offs, 1U); 			///4:4:4
		write_register(base_address + VPSS_clamp_offs, 0U);
		write_register(base_address + VPSS_clip_offs, (1<<(data_width))-1);

		write_register(base_address + VPSS_w_offs, width);
		write_register(base_address + VPSS_h_offs, height);
		write_register(base_address + VPSS_ctrl_offs, VPSS_rst_bit | VPSS_st_bit);

		return 0;
	}
}
