/**
 * @file v_proc_ss.c
 * @brief Library for video processing subsystem of Xilinx.
 * 
 * @date 	February, 2024
 * @author	Victor Morales, Sergio Cuenca
 * @company Embention
 */


#include "v_proc_ss.h"


static void set_reg(uint32_t addr, uint32_t val){

    mem_map mm;
	memmap_init(&mm, addr);
	
	memmap_write(mm, addr, val);

	memmap_close(mm);

}


uint8_t v_proc_ss_setup(v_proc_ss_conf config)
{
	// Set coef scalar factor 4096
	// Set offset scalar factor 256
	// Set coeff values depending ranges

#ifdef COLOR_IN_YCBCR_16_235

	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K11_OFFS, (int32_t)( 0.114*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K12_OFFS, (int32_t)( 0.587*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K13_OFFS, (int32_t)( 0.299*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K21_OFFS, (int32_t)( 0.5*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K22_OFFS, (int32_t)(-0.331264*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K23_OFFS, (int32_t)(-0.168736*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K31_OFFS, (int32_t)( -0.081312*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K32_OFFS, (int32_t)(-0.41866*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K33_OFFS, (int32_t)( 0.5*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_R_OFFS_OFFS, (0));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_G_OFFS_OFFS, (128));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_B_OFFS_OFFS, (128));

#elif COLOR_IN_YCBCR_0_255
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K11_OFFS, (int32_t)( 0.2568*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K12_OFFS, (int32_t)( 0.5041*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K13_OFFS, (int32_t)( 0.0979*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K21_OFFS, (int32_t)(-0.1482*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K22_OFFS, (int32_t)(-0.2910*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K23_OFFS, (int32_t)( 0.4393*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K31_OFFS, (int32_t)( 0.4393*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K32_OFFS, (int32_t)(-0.3678*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K33_OFFS, (int32_t)(-0.0714*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_R_OFFS_OFFS, (16*1));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_G_OFFS_OFFS, (128*1));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_B_OFFS_OFFS, (128*1));

#elif NO_COLOR
	// NO COLOR TRANSFORMATION
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K11_OFFS, (int32_t)(1*(float)4096));//red
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K12_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K13_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K21_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K22_OFFS, (int32_t)(1*(float)4096));//green
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K23_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K31_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K32_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K33_OFFS, (int32_t)(1*(float)4096));//blue
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_R_OFFS_OFFS, (0));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_G_OFFS_OFFS, (0));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_B_OFFS_OFFS, (0));
#else
	// NO COLOR TRANSFORMATION
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K11_OFFS, (int32_t)( 0.299*(float)4096));//red
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K12_OFFS, (int32_t)( 0.587*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K13_OFFS, (int32_t)( 0.114*(float)4096));

	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K21_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K22_OFFS, (int32_t)(0*(float)4096));//green
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K23_OFFS, (int32_t)(0*(float)4096));

	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K31_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K32_OFFS, (int32_t)(0*(float)4096));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_K33_OFFS, (int32_t)(0*(float)4096));//blue
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_R_OFFS_OFFS, (0));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_G_OFFS_OFFS, (0));
	set_reg(config.dev_base_addr + V_PROC_SS_COEFF_B_OFFS_OFFS, (0));
#endif
	set_reg(config.dev_base_addr + V_PROC_SS_IN_V_FRT_OFFS, 0U); // RGB
	set_reg(config.dev_base_addr + V_PROC_SS_OUT_V_FRT_OFFS, 1U); //4:4:4
	set_reg(config.dev_base_addr + V_PROC_SS_CLAMP_MIN_OFFS, 0U);
	set_reg(config.dev_base_addr + V_PROC_SS_CLIP_MAX_OFFS, (1<<(config.data_width))-1);

	set_reg(config.dev_base_addr + V_PROC_SS_WIDTH_OFFS, config.width);
	set_reg(config.dev_base_addr + V_PROC_SS_HEIGHT_OFFS, config.height);
	set_reg(config.dev_base_addr + V_PROC_SS_CTRL_OFFS, V_PROC_SS_CTRL_AUTO_RST_BIT | V_PROC_SS_CTRL_START_BIT);

	return 0;
}

