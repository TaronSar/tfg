/**
 * @file imx296.c
 * @brief Library for IMX296LQR-C sensor.
 * 
 * @date 	January, 2024
 * @author	Victor Morales
 * @company Embention
 */


#include "imx296.h"
#include <time.h>


static uint32_t i2c_fd;

static uint8_t write_byte(uint16_t addr, uint8_t val);
static uint8_t write_halfword(uint16_t addr, uint16_t val);
static uint8_t read_byte(uint16_t addr, uint8_t *reg);

static uint8_t undocumented_sequence();

uint8_t imx296_setup(imx296_conf config){
	uint16_t model_id;
    uint8_t reg;
	uint8_t ret_value = 0;


	if(((config.crop_left + config.width) > IMX296_MAX_WIDTH) || ((config.crop_top + config.height) > IMX296_MAX_HEIGHT)){
		ret_value = 1;
		print("Image dimensions too big\n");
	}
	else{

    	// INIT i2c device
		i2c_init(&i2c_fd, I2C_DEVICE_NUM);
		
		undocumented_sequence();
	
		if((config.width != IMX296_MAX_WIDTH) || (config.height != IMX296_MAX_HEIGHT))
		{
			write_byte(IMX296_FID0_ROI_ADDR, 0x3U);
			write_halfword(IMX296_FID0_ROIPH1_ADDR, config.crop_left);
			write_halfword(IMX296_FID0_ROIPV1_ADDR, config.crop_top);
			write_halfword(IMX296_FID0_ROIWH1_ADDR, config.width);
			write_halfword(IMX296_FID0_ROIWV1_ADDR, config.height);
			write_halfword(IMX296_MIPIC_AREA3W_ADDR, config.height);
			if(config.shs >= IMX296_MAX_SHS)
			{
				imx296_set_shs(IMX296_MAX_SHS);
			}
			else
			{
				imx296_set_shs(config.shs);
			}
		}
		else{
			write_byte(IMX296_FID0_ROI_ADDR, 0x00U);
			write_byte(IMX296_MIPIC_AREA3W_ADDR, (uint8_t)1088);
			write_byte(IMX296_MIPIC_AREA3W_ADDR + 1U, (uint8_t)(1088>>8U));		
			if(config.shs >= config.height + 30)
			{
				imx296_set_shs(config.height + 29);
			}
			else
			{
				imx296_set_shs(config.shs);
			}
		}

		//write_byte(IMX296_CTRL0D_ADDR, 34U); // Included in linux driver, corrupt image
	
		write_halfword(IMX296_HMAX_ADDR, (uint16_t)1100);
		write_halfword(IMX296_VMAX_ADDR, (uint16_t)(config.height+30U));
	
		write_byte(IMX296_INCKSEL_BASE_ADDR, 0x80U);
		write_byte(IMX296_INCKSEL_BASE_ADDR + 1, 0x0FU);
		write_byte(IMX296_INCKSEL_BASE_ADDR + 2, 0x80U);
		write_byte(IMX296_INCKSEL_BASE_ADDR + 3, 0x0CU);
	
		write_byte(IMX296_GTTABLENUM_ADDR, 0x05U);
		write_byte(IMX296_CTRL418C_ADDR, 232U);
	
		write_byte(IMX296_GAINDLY_ADDR, 0x09U);
		write_byte(IMX296_BLKLEVEL_ADDR, 0x3CU);
		write_halfword(IMX296_BLKLEVEL_ADDR, (uint16_t)0U);
	
		//Stream on
		write_byte(IMX296_CTRL00_ADDR, 0U);
		usleep(5000);
	
		write_byte(IMX296_CTRL0B_ADDR, 0U);
		write_byte(IMX296_LOWLAGTRG_ADDR, 0U);
	
		write_byte(IMX296_CTRL0A_ADDR, 0U);
	
		// Normal mode
	
		usleep(28000); // Internal regulator stabilization  IMX296LQR-C Datasheet Page.77
    	// CHECK imx296 MODEL ID
		read_byte(IMX296_INFO_TYPE_ADDR, &reg);
	
    	model_id = reg;

		if(config.gain >= IMX296_MAX_GAIN)
		{
			imx296_set_gain(IMX296_MAX_GAIN);
		}
		else
		{
			imx296_set_gain(config.gain);
		}
	
    	if(model_id == IMX296LQ_ID){
    	    print("Camera (IMX296LQ-C) detected and configured with exposure time!\n");

    	}
    	else{
    	    print("Camera not detected!\n");
    	    ret_value = 2;
    	}
	}
	
    return ret_value;
}

static uint8_t undocumented_sequence(){
// https://github.com/raspberrypi/linux/blob/rpi-6.1.y/drivers/media/i2c/imx296.c
    write_byte((0x3005), 0xf0 );
	write_byte((0x309e), 0x04 );
	write_byte((0x30a0), 0x04 );
	write_byte((0x30a1), 0x3c );
	write_byte((0x30a4), 0x5f );
	write_byte((0x30a8), 0x91 );
	write_byte((0x30ac), 0x28 );
	write_byte((0x30af), 0x09 );
	write_byte((0x30df), 0x00 );
	write_byte((0x3165), 0x00 );
	write_byte((0x3169), 0x10 );
	write_byte((0x316a), 0x02 );
	write_byte((0x31c8), 0xf3 );/*posure-related */
	write_byte((0x31d0), 0xf4 );/*posure-related */
	write_byte((0x321a), 0x00 );
	write_byte((0x3226), 0x02 );
	write_byte((0x3256), 0x01 );
	write_byte((0x3541), 0x72 );
	write_byte((0x3516), 0x77 );
	write_byte((0x350b), 0x7f );
	write_byte((0x3758), 0xa3 );
	write_byte((0x3759), 0x00 );
	write_byte((0x375a), 0x85 );
	write_byte((0x375b), 0x00 );
	write_byte((0x3832), 0xf5 );
	write_byte((0x3833), 0x00 );
	write_byte((0x38a2), 0xf6 );
	write_byte((0x38a3), 0x00 );
	write_byte((0x3a00), 0x80 );
	write_byte((0x3d48), 0xa3 );
	write_byte((0x3d49), 0x00 );
	write_byte((0x3d4a), 0x85 );
	write_byte((0x3d4b), 0x00 );
	write_byte((0x400e), 0x58 );
	write_byte((0x4014), 0x1c );
	write_byte((0x4041), 0x2a );
	write_byte((0x40a2), 0x06 );
	write_byte((0x40c1), 0xf6 );
	write_byte((0x40c7), 0x0f );
	write_byte((0x40c8), 0x00 );
	write_byte((0x4174), 0x00 );
	return 0;
}

void imx296_set_shs(uint32_t shs){
	int result = 0;
	result = write_byte(IMX296_SHS_0, (uint8_t)(shs & 0xFFU));
	result += write_byte(IMX296_SHS_1, (uint8_t)((shs >> 8) & 0xFFU));
	result += write_byte(IMX296_SHS_2, (uint8_t)((shs >> 16) & 0xFFU));
	if(result != 0)
	{ 
		print("Fail setting shs to %d.\n", shs);

	}
	

}

void imx296_set_gain(uint16_t gain)
{
	int result = 0;
	result = write_halfword(IMX296_GAIN_ADDR, gain);
	if(result != 0)
	{ 
		print("Fail setting gain to %d.\n", gain);
	}
}


void imx296_set_blklevel(uint16_t blklevel)
{
	int result = 0;
	result = write_halfword(IMX296_BLKLEVEL_ADDR, blklevel);
	if(result != 0)
	{ 
		print("Fail setting black level to %d.\n", blklevel);
	}
}

static uint8_t write_byte(uint16_t addr, uint8_t val){
    int ret = 0;
    
    if(i2c_write_reg(i2c_fd, I2C_DEVICE_ADDR, addr, val) != 0){
        print("Error writing imx296 register 0x%04X.\n", addr);
        ret = 1;
    }

    return ret;
}

static uint8_t write_halfword(uint16_t addr, uint16_t val){
    int ret = 0;

    if(i2c_write_reg(i2c_fd, I2C_DEVICE_ADDR, addr, val) != 0){
        print("Error writing imx296 register 0x%04X.\n", addr);
        ret = 1;
    }
	if(i2c_write_reg(i2c_fd, I2C_DEVICE_ADDR, addr + 1, (uint8_t)(val >> 8U)) != 0){
        print("Error writing imx296 register 0x%04X.\n", addr);
        ret = 1;
    }

    return ret;
}

static uint8_t read_byte(uint16_t addr, uint8_t *reg){
    int ret = 0;

    if(i2c_read_reg(i2c_fd, I2C_DEVICE_ADDR, addr, reg) != 0){
        print("Error reading imx296 register 0x%04X.\n", addr);
        ret = 1;
    }

    return ret;
}
