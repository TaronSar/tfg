///    \file Demosaic.cpp
///
///    \date 28 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    Demosaic class implementation.
///


#include <Demosaic.h>


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
    
    Demosaic::Demosaic(Uint32 base_addr)
    {
        /// Setup parameters
        base_address = base_addr;
    }


    /// ************************************************************************************
    /// COPROC configuration for Demosaic core
    void Demosaic::config(Uint32 vid_width, Uint32 vid_height, Uint8 bayer_phase)
    {
        set_hw_width(vid_width);
        set_hw_height(vid_height);
        set_bayer_ph(bayer_phase);
        en_auto_rst();
        start();
    }


    /// ************************************************************************************

    void Demosaic::start()
    {
        Uint32 data;

        data = read_register(base_address + Dem_ap_addr) & Dem_start_data;
        write_register((base_address + Dem_ap_addr), (data | 0x01));
    }


    /// ************************************************************************************

    void Demosaic::en_auto_rst()
    {
        write_register((base_address + Dem_ap_addr), Dem_start_data);
    }


    /// ************************************************************************************

    void Demosaic::set_hw_width(Uint32 data)
    {
        write_register((base_address + Dem_dw_addr), data);
    }


    /// ************************************************************************************
    /// Sets demosaic HW height
    void Demosaic::set_hw_height(Uint32 data)
    {
        write_register((base_address + Dem_dh_addr), data);
    }


    /// ************************************************************************************

    void Demosaic::set_bayer_ph(Uint32 data)
    {
        write_register((base_address + Dem_bd_addr), data);
    }

}
