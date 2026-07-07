///    \file Gamma_LUT.cpp
///
///    \date 2 sept. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    \copyright   Embention S.A.
///
///    Gamma_LUT class implementation.
///



#include <Gamma_LUT.h>


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
    /// Set base address for Gamma LUT core
    Gamma_LUT::Gamma_LUT(Uintptr base_addr)
    {
        /// Setup parameters
        base_address = base_addr;
    }


    /// ************************************************************************************
    /// Gamma LUT general configuration (wrapper)
    void Gamma_LUT::config(Uint32 vid_width, Uint32 vid_height, Uint8 data_width, Real gamma_value)
    {
        Uint16* gamma_reg;
        gamma_reg = reinterpret_cast<Uint16*>(malloc((1 << data_width) * sizeof(Uint16)));
        int i;

        // GAMMA LUT CONFIGURATION
        //------------ Gamma calc
        for(i = 0; i<(1<<data_width); i++)
        {
            gamma_reg[i] = (pow((i / static_cast<Real>(1<<data_width)), (1/gamma_value)) * static_cast<Real>(1<<data_width));
        }
        //----------

        set_width(vid_width);
        set_height(vid_height);
        set_vid_format(0x00);
        
        write_GLUT0_B(0,reinterpret_cast<char*>(gamma_reg), (2<<data_width));
        write_GLUT1_B(0,reinterpret_cast<char*>(gamma_reg), (2<<data_width));
        write_GLUT2_B(0,reinterpret_cast<char*>(gamma_reg), (2<<data_width));

        start();
        en_auto_rst();
    }


    /// ************************************************************************************

    void Gamma_LUT::start()
    {
        Uint32 data;

        data = read_register(base_address + GLUT_AP_addr) & GLUT_st_val;
        write_register((base_address + GLUT_AP_addr), static_cast<Uint32>(data | 0x01));
    }


    /// ************************************************************************************

    void Gamma_LUT::en_auto_rst()
    {
        write_register((base_address + GLUT_AP_addr), static_cast<Uint32>(GLUT_st_val));
    }


    /// ************************************************************************************

    void Gamma_LUT::set_width(Uint32 data)
    {
        write_register((base_address, GLUT_dw_addr), data);
    }


    /// ************************************************************************************

    void Gamma_LUT::set_height(Uint32 data)
    {
        write_register((base_address + GLUT_dh_addr), data);
    }


    /// ************************************************************************************

    void Gamma_LUT::set_vid_format(Uint32 data)
    {
        write_register((base_address + GLUT_dv_addr), data);
    }


    /// ************************************************************************************

    Uint32 Gamma_LUT::get_GLUT0_B()
    {
        Uint32 result = GLUT0_highaddr - GLUT0_baseaddr + 1;
        return result;
    }


    /// ************************************************************************************

    Uint32 Gamma_LUT::write_GLUT0_B(int offset, char *data, int length)
    {
        Uint32 result = length;

        if ((offset + length) > get_GLUT0_B())
        {
            result = 0;
        }    
        else
        {
            for (int i = 0; i < length; i++)
            {
                Uint32 addr = static_cast<Uint32>(base_address + GLUT0_baseaddr + offset + i);

                /// Only write 1 byte
                Uint32 value = read_register(addr) & bits8_mask;
                Uint32 new_value = value | static_cast<Uint32>(*(data + i));

                write_register(addr,new_value);
            }
        }

            
        return result;
    }


    /// ************************************************************************************

    Uint32 Gamma_LUT::get_GLUT1_B()
    {
        Uint32 result = GLUT1_highaddr - GLUT1_baseaddr + 1;
        return result;
    }


    /// ************************************************************************************

    Uint32 Gamma_LUT::write_GLUT1_B(int offset, char *data, int length)
    {
        Uint32 result = length;

        int i;

        if ((offset + length) > get_GLUT1_B())
        {
            result = 0;
        }
        else
        {
            for (int i = 0; i < length; i++)
            {
                Uint32 addr = static_cast<Uint32>(base_address + GLUT1_baseaddr + offset + i);

                /// Only write 1 byte
                Uint32 value = read_register(addr) & bits8_mask;
                Uint32 new_value = value | static_cast<Uint32>(*(data + i));

                write_register(addr,new_value);
            }
        }

        return result;
    }


    /// ************************************************************************************

    Uint32 Gamma_LUT::get_GLUT2_B()
    {
        Uint32 result = GLUT2_highaddr - GLUT2_baseaddr + 1;
        return result;
    }


    /// ************************************************************************************

    Uint32 Gamma_LUT::write_GLUT2_B(int offset, char *data, int length)
    {
        Uint32 result = length;
    
        if ((offset + length) > get_GLUT2_B())
        {
            result = 0;
        }
        else
        {
            for (int i = 0; i < length; i++)
            {
                Uint32 addr = static_cast<Uint32>(base_address + GLUT2_baseaddr + offset + i);

                /// Only write 1 byte
                Uint32 value = read_register(addr) & bits8_mask;
                Uint32 new_value = value | static_cast<Uint32>(*(data + i));

                write_register(addr,new_value);
            }
        }

        return result;
    }


}