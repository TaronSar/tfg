///    \file IMX296.cpp
///
///    \date 26 ago. 2024
///
///    \author      Caio Iriarte, cis11 (at) embention.com
///    Company      Embention S.A.
///
///    IMX296 class implementation.
///


#include <IMX296.h>
#include <Sleep.h>


/// Constants for sequence
const Uint32 dir_1 = 0x3005U;
const Uint32 dir_2 = 0x309EU;
const Uint32 dir_3 = 0x30A0U;
const Uint32 dir_4 = 0x30A1U;
const Uint32 dir_5 = 0x30A4U;
const Uint32 dir_6 = 0x30A8U;
const Uint32 dir_7 = 0x30ACU;
const Uint32 dir_8 = 0x30AFU;
const Uint32 dir_9 = 0x30DFU;
const Uint32 dir_10 = 0x3165U;
const Uint32 dir_11 = 0x3169U;
const Uint32 dir_12 = 0x316AU;
const Uint32 dir_13 = 0x31C8U;
const Uint32 dir_14 = 0x31D0U;
const Uint32 dir_15 = 0x321AU;
const Uint32 dir_16 = 0x3226U;
const Uint32 dir_17 = 0x3256U;
const Uint32 dir_18 = 0x3541U;
const Uint32 dir_19 = 0x3516U;
const Uint32 dir_20 = 0x350BU;
const Uint32 dir_21 = 0x3758U;
const Uint32 dir_22 = 0x3759U;
const Uint32 dir_23 = 0x375AU;
const Uint32 dir_24 = 0x375BU;
const Uint32 dir_25 = 0x3832U;
const Uint32 dir_26 = 0x3833U;
const Uint32 dir_27 = 0x38A2U;
const Uint32 dir_28 = 0x38A3U;
const Uint32 dir_29 = 0x3A00U;
const Uint32 dir_30 = 0x3D48U;
const Uint32 dir_31 = 0x3D49U;
const Uint32 dir_32 = 0x3D4AU;
const Uint32 dir_33 = 0x3D4BU;
const Uint32 dir_34 = 0x400EU;
const Uint32 dir_35 = 0x4014U;
const Uint32 dir_36 = 0x4041U;
const Uint32 dir_37 = 0x40A2U;
const Uint32 dir_38 = 0x40C1U;
const Uint32 dir_39 = 0x40C7U;
const Uint32 dir_40 = 0x40C8U;
const Uint32 dir_41 = 0x4174U;


/// Sequence values written
const Uint8 val_seq1 = 0xF0U;
const Uint8 val_seq2 = 0x04U;
const Uint8 val_seq3 = 0x3CU;
const Uint8 val_seq4 = 0x5FU;
const Uint8 val_seq5 = 0x91U;
const Uint8 val_seq6 = 0x28U;
const Uint8 val_seq7 = 0x09U;
const Uint8 val_seq8 = 0x00U;
const Uint8 val_seq9 = 0x10U;
const Uint8 val_seq10 = 0x02U;
const Uint8 val_seq11 = 0xF3U;
const Uint8 val_seq12 = 0xF4U;
const Uint8 val_seq13 = 0x01U;
const Uint8 val_seq14 = 0x72U;
const Uint8 val_seq15 = 0x77U;
const Uint8 val_seq16 = 0x7FU;
const Uint8 val_seq17 = 0xA3U;
const Uint8 val_seq18 = 0x85U;
const Uint8 val_seq19 = 0xF5U;
const Uint8 val_seq20 = 0xF6U;
const Uint8 val_seq21 = 0x80U;
const Uint8 val_seq22 = 0x58U;
const Uint8 val_seq23 = 0x1CU;
const Uint8 val_seq24 = 0x2AU;
const Uint8 val_seq25 = 0x06U;
const Uint8 val_seq26 = 0xF6U;
const Uint8 val_seq27 = 0x0FU;


/// Values for setup
const Uint8 set_val1 = 0x3U;
const Uint8 set_val2 = 1088U;
const Uint8 set_val3 = (1088 >> 8U);
const Uint8 set_val4 = 0x80U;
const Uint8 set_val5 = 0x0FU;
const Uint8 set_val6 = 0x0CU;
const Uint8 set_val7 = 0x05U;
const Uint8 set_val8 = 232U;
const Uint8 set_val9 = 0x09U;
const Uint8 set_val10 = 0x3CU;


namespace Zusp
{
	static void write_byte(I2C &i2c, Uint32 addr, Uint8 val);
	static void write_halfword(I2C &i2c, Uint32 addr, Uint16 val);
	static void read_byte(I2C &i2c, Uint32 addr, Uint8 *reg);
	static void undocumented_sequence(I2C &i2c);

	
	/// ************************************************************************************

	IMX296::IMX296(I2C& i2cport, Uint16 width, Uint16 height, Uint16 crop_top,
					Uint16 crop_left, Uint16 bayer_phase, Uint32 shs) : port(i2cport)
	{
		imx_bayer_phase = bayer_phase;
		imx_crop_left = crop_left;
		imx_crop_top = crop_top;
		imx_height = height;
		imx_width = width;
		imx_shs = shs;
	}
	
	
	/// ************************************************************************************
    
	Uint8 IMX296::setup()
	{
		Uint16 model_id;
		Uint8 reg;
		Uint8 ret_value = 0;


		if(((imx_crop_left + imx_width) > IMX296_max_w) ||		///	Images too big
			((imx_crop_top + imx_height) > IMX296_max_h))
		{
			ret_value = 1;
		}
		else
		{
			undocumented_sequence(port);
		
			if((imx_width != IMX296_max_w) || (imx_height != IMX296_max_h))
			{
				write_byte(port, IMX296_FD0_addr, set_val1);
				write_halfword(port, IMX296_PH1_addr, imx_crop_left);
				write_halfword(port, IMX296_PV1_addr, imx_crop_top);
				write_halfword(port, IMX296_WH1_addr, imx_width);
				write_halfword(port, IMX296_WV1_addr, imx_height);
				write_halfword(port, IMX296_a3W_addr, imx_height);
				if(imx_shs >= IMX296_max_shs)
				{
					set_shs(IMX296_max_shs);
				}
				else
				{
					set_shs(imx_shs);
				}
			}
			else
			{
				write_byte(port, IMX296_FD0_addr, 0U);
				write_byte(port, IMX296_a3W_addr, set_val2);
				write_byte(port, IMX296_a3W_addr + 1U, set_val3);		
				if(imx_shs >= imx_height + IMX296_img_c1)
				{
					set_shs(static_cast<Uint32>(imx_height + IMX296_img_c2));
				}
				else
				{
					set_shs(imx_shs);
				}
			}

			/// write_byte(i2c, IMX296_CTRL0D_ADDR, 34U); /// Included in linux driver, corrupt image
		
			write_halfword(port, IMX296_hm_addr, IMX296_half_wd);
			write_halfword(port, IMX296_vm_addr, static_cast<Uint16>(imx_height + IMX296_hw_offs));

			Uint32 aux_addr = IMX296_is_addr;
			write_byte(port, aux_addr, set_val4);
			aux_addr += 1;
			write_byte(port, aux_addr, set_val5);
			aux_addr += 1;
			write_byte(port, aux_addr, set_val4);
			aux_addr += 1;
			write_byte(port, aux_addr, set_val6);
		
			write_byte(port, IMX296_GT_addr, set_val7);
			write_byte(port, IMX296_418_addr, set_val8);
		
			write_byte(port, IMX296_gd_addr, set_val9);
			write_byte(port, IMX296_BLK_addr, set_val10);
			write_halfword(port, IMX296_BLK_addr, static_cast<Uint16>(0U));
		
			/// Stream on
			write_byte(port, IMX296_00_addr, 0U);
			Sleep::sleep_us(IMG296_delay1);
		
			write_byte(port, IMX296_0B_addr, 0U);
			write_byte(port, IMX296_TRG_addr, 0U);
		
			write_byte(port, IMX296_0A_addr, 0U);
		
			/// Normal mode
		
			Sleep::sleep_us(IMG296_delay2); 		/// Internal regulator stabilization  IMX296LQR-C Datasheet Page.77
			
			/// CHECK IMX296 MODEL ID
			read_byte(port, IMX296_i_addr, &reg);
		
			model_id = reg;
		}
		
		return ret_value;
	}


	/// ************************************************************************************
	
	void IMX296::set_shs(Uint32 shs)
	{
		write_byte(port, IMX296_shs_0, static_cast<Uint8>(shs & IMX296_mask));
		write_byte(port, IMX296_shs_1, static_cast<Uint8>((shs >> value_8b) & IMX296_mask));
		write_byte(port, IMX296_shs_2, static_cast<Uint8>((shs >> value_16b) & IMX296_mask));
	}


	/// ************************************************************************************
	///	Undocumented sequence to be written through I2C controller
	void undocumented_sequence(Zusp::I2C &i2c)
	{
		write_byte(i2c, dir_1, val_seq1);   		/// 0x3005, 0xF0
		write_byte(i2c, dir_2, val_seq2);   		/// 0x309E, 0x04
		write_byte(i2c, dir_3, val_seq2);   		/// 0x30A0, 0x04
		write_byte(i2c, dir_4, val_seq3);   		/// 0x30A1, 0x3C
		write_byte(i2c, dir_5, val_seq4);   		/// 0x30A4, 0x5F
		write_byte(i2c, dir_6, val_seq5);   		/// 0x30A8, 0x91
		write_byte(i2c, dir_7, val_seq6);   		/// 0x30AC, 0x28
		write_byte(i2c, dir_8, val_seq7);   		/// 0x30AF, 0x09
		write_byte(i2c, dir_9, val_seq8);   		/// 0x30DF, 0x00
		write_byte(i2c, dir_10, val_seq8);  		/// 0x3165, 0x00
		write_byte(i2c, dir_11, val_seq9);  		/// 0x3169, 0x10
		write_byte(i2c, dir_12, val_seq10); 		/// 0x316A, 0x02
		write_byte(i2c, dir_13, val_seq11); 		/// 0x31C8, 0xF3
		write_byte(i2c, dir_14, val_seq12); 		/// 0x31D0, 0xF4
		write_byte(i2c, dir_15, val_seq8);  		/// 0x321A, 0x00
		write_byte(i2c, dir_16, val_seq10); 		/// 0x3226, 0x02
		write_byte(i2c, dir_17, val_seq13); 		/// 0x3256, 0x01
		write_byte(i2c, dir_18, val_seq14); 		/// 0x3541, 0x72
		write_byte(i2c, dir_19, val_seq15); 		/// 0x3516, 0x77
		write_byte(i2c, dir_20, val_seq16); 		/// 0x350B, 0x7F
		write_byte(i2c, dir_21, val_seq17); 		/// 0x3758, 0xA3
		write_byte(i2c, dir_22, val_seq8);  		/// 0x3759, 0x00
		write_byte(i2c, dir_23, val_seq18); 		/// 0x375A, 0x85
		write_byte(i2c, dir_24, val_seq8);  		/// 0x375B, 0x00
		write_byte(i2c, dir_25, val_seq19); 		/// 0x3832, 0xF5
		write_byte(i2c, dir_26, val_seq8);  		/// 0x3833, 0x00
		write_byte(i2c, dir_27, val_seq20); 		/// 0x38A2, 0xF6
		write_byte(i2c, dir_28, val_seq8);  		/// 0x38A3, 0x00
		write_byte(i2c, dir_29, val_seq21); 		/// 0x3A00, 0x80
		write_byte(i2c, dir_30, val_seq17); 		/// 0x3D48, 0xA3
		write_byte(i2c, dir_31, val_seq8);  		/// 0x3D49, 0x00
		write_byte(i2c, dir_32, val_seq18); 		/// 0x3D4A, 0x85
		write_byte(i2c, dir_33, val_seq8);  		/// 0x3D4B, 0x00
		write_byte(i2c, dir_34, val_seq22); 		/// 0x400E, 0x58
		write_byte(i2c, dir_35, val_seq23); 		/// 0x4014, 0x1C
		write_byte(i2c, dir_36, val_seq24); 		/// 0x4041, 0x2A
		write_byte(i2c, dir_37, val_seq25); 		/// 0x40A2, 0x06
		write_byte(i2c, dir_38, val_seq20); 		/// 0x40C1, 0xF6
		write_byte(i2c, dir_39, val_seq27); 		/// 0x40C7, 0x0F
		write_byte(i2c, dir_40, val_seq8);  		/// 0x40C8, 0x00
		write_byte(i2c, dir_41, val_seq8);  		/// 0x4174, 0x00
	}




	///	Write byte from I2C controller
	void write_byte(I2C &i2c, Uint32 addr, Uint8 val)
	{
		i2c.start_write(addr,1,&val);
	}


	///	Write halfword from I2C controller
	void write_halfword(I2C &i2c, Uint32 addr, Uint16 val)
	{
		/// Separate halfword in two byte variables
		Uint8 data[2];
		data[0] = static_cast<Uint8>(val & IMX296_mask);       		/// LSB (less significant)
		data[1] = static_cast<Uint8>((val >> value_8b) & IMX296_mask); 	/// MSB (most significant)

		/// Call write for 1st byte
		i2c.start_write(addr,1,&data[0]);
		
		///	Call write for 2nd byte
		i2c.start_write((addr+1),1,&data[1]);
	}


	/// Read byte from I2C controller data register
	void read_byte(Zusp::I2C &i2c, Uint32 addr, Uint8 *reg)
	{
		i2c.start_read(addr,1,reg);
	}

}