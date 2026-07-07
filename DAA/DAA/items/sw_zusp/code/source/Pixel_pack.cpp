///    \file Pixel_Pack.cpp
///
///    \date 27 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    Pixel_Pack class implementation.
///


#include <Pixel_pack.h>
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

	Pixel_pack::Pixel_pack(Uint32 addr, Pixel_pack_mode pixel_mode)
	{
		base_address = addr;
		mode = pixel_mode;
	}


	/// ************************************************************************************
	///	Pixel_Pack setup for configuration
	Uint8 Pixel_pack::setup()
	{	
		Uint32 check, ret;
		
		write_register(base_address + Pixel_pack_offs , static_cast<Uint32>(mode));
		check = read_register(base_address + Pixel_pack_offs);

		if(check == static_cast<Uint32>(mode))
		{
			ret = 0;
		}
		else
		{
			ret = 1;
		}

		return ret;
	}
}

