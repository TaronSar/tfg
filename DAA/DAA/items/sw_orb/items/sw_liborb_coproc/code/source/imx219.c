//----------------------------------------------------------------------//
//                         IMX219 Linux Driver                          //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#include "imx219.h"


static uint32_t i2c_fd;

static uint8_t write_reg(uint16_t addr, uint8_t val);
static uint8_t read_reg(uint16_t addr, uint8_t *reg);

static void access_command_sequence();


uint8_t imx219_init(){
	uint16_t model_id;
    uint8_t reg;

    // INIT i2c device
	i2c_init(&i2c_fd, I2C_DEVICE_NUM);

    // CHECK IMX219 MODEL ID
	read_reg(IMX219_MODEL_ID_H, &reg);
    model_id = reg;

    read_reg(IMX219_MODEL_ID_L, &reg);
    model_id = ((model_id << 8) & 0xFF00) | reg;
    
    if(model_id == IMX219_ID){
        print("Camera (IMX219) detected!\n");
    }
    else{
        print("Camera not detected!\n");
        return 1;
    }

    return 0;
}


uint8_t imx219_config(){

    access_command_sequence();

    write_reg(0x0114, 0x01); // 2-wire csi
	write_reg(0x0128, 0x00); // auto MIPI global timing
	write_reg(0x012A, 0x18); // INCK freq: 24.0Mhz
	write_reg(0x012B, 0x00);
	write_reg(0x0160, 0x04); // frame length lines = 1113
	write_reg(0x0161, 0x59);
	write_reg(0x0162, 0x0D); // line length pixels = 3448
	write_reg(0x0163, 0x78);
	write_reg(0x0164, 0x02); // x-start address = 680
	write_reg(0x0165, 0xA8);
	write_reg(0x0166, 0x0A); // x-end address = 2599
	write_reg(0x0167, 0x27);
	write_reg(0x0168, 0x02); // y-start address = 692
	write_reg(0x0169, 0xB4);
	write_reg(0x016A, 0x06); // y-end address = 1771
	write_reg(0x016B, 0xEB);
	write_reg(0x016C, 0x07); // x-output size = 1920
	write_reg(0x016D, 0x80);
	write_reg(0x016E, 0x04); // y-output size = 1080
	write_reg(0x016F, 0x38);
	write_reg(0x0170, 0x01); //
	write_reg(0x0171, 0x01);
	write_reg(0x0174, 0x00);
	write_reg(0x0175, 0x00);
	write_reg(0x018C, 0x0A);
	write_reg(0x018D, 0x0A);
	write_reg(0x0301, 0x05); // video timing pixel clock divider value = 5
	write_reg(0x0303, 0x01); // video timing system clock divider value = 1
	write_reg(0x0304, 0x03); // external clock 24-27MHz
	write_reg(0x0305, 0x03); // external clock 24-27MHz
	write_reg(0x0306, 0x00); // PLL Video Timing system multiplier value = 57
	write_reg(0x0307, 0x39);
	write_reg(0x0309, 0x0A); // output pixel clock divider value = 10
	write_reg(0x030B, 0x01); // output system clock divider value = 1
	write_reg(0x030C, 0x00); // PLL output system multiplier value = 114
	write_reg(0x030D, 0x72);
	write_reg(0x455E, 0x00);
	write_reg(0x471E, 0x4B);
	write_reg(0x4767, 0x0F);
	write_reg(0x4750, 0x14);
	write_reg(0x4540, 0x00);
	write_reg(0x47B4, 0x14);
	write_reg(0x4713, 0x30);
	write_reg(0x478B, 0x10);
	write_reg(0x478F, 0x10);
	write_reg(0x4793, 0x10);
	write_reg(0x4797, 0x0E);
	write_reg(0x479B, 0x0E);
	write_reg(0x0100, 0x01);

    write_reg(0x0157, 232);

    print("Camera configured\n");

    return 0;
}



static void access_command_sequence(){
    // Access command sequence p.41 SONY IMX219PQH5-C document
    write_reg(0x30EB, 0x05);
	write_reg(0x30EB, 0x0C);
	write_reg(0x300A, 0xFF);
	write_reg(0x300B, 0xFF);
	write_reg(0x30EB, 0x05);
	write_reg(0x30EB, 0x09);
}




static uint8_t write_reg(uint16_t addr, uint8_t val){
    
    if(i2c_write_reg(i2c_fd, I2C_DEVICE_ADDR, addr, val) != 0){
        print("Error writing imx219 register 0x%04X.", addr);
        return 1;
    }

    return 0;
}


static uint8_t read_reg(uint16_t addr, uint8_t *reg){

    if(i2c_read_reg(i2c_fd, I2C_DEVICE_ADDR, addr, reg) != 0){
        print("Error reading imx219 register 0x%04X.", addr);
        return 1;
    }

    return 0;
}
