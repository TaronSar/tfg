//----------------------------------------------------------------------//
//                         I2C Linux Driver                             //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#include "i2c.h"

uint32_t i2c_init(uint32_t *i2c_fd, uint8_t sel_i2c){

	char i2c_name[20] = "/dev/i2c-";
	char dev_num [200];
	sprintf(dev_num, "%u", sel_i2c);
	strcat(i2c_name,dev_num);
    
    //print("i2c device: %s\n", i2c_name);

	if ((*i2c_fd = open(i2c_name, O_RDWR)) < 0) {
		print("Error to open i2c connection (i2c-%d) \n",sel_i2c);
		return -1;
	}

	return 0;
} 


uint32_t i2c_read_reg(uint32_t i2c_fd, uint8_t addr_dev, uint16_t addr_reg, uint8_t *reg){


	uint8_t inbuf[2];
	uint8_t outbuf[2];

    struct i2c_msg msgs[2];
    struct i2c_rdwr_ioctl_data msgset[1];

    outbuf[0] = addr_reg >> 8;
    outbuf[1] = addr_reg & 0xFF;

    msgs[0].addr = addr_dev;
    msgs[0].flags = 0;
    msgs[0].len = 2;
    msgs[0].buf = outbuf;

    msgs[1].addr = addr_dev;
    msgs[1].flags = I2C_M_RD;
    msgs[1].len = 1;
    msgs[1].buf = inbuf;

    msgset[0].msgs = msgs;
    msgset[0].nmsgs = 2;

    inbuf[0] = 0x00;
    
    if (ioctl(i2c_fd, I2C_RDWR, &msgset) < 0) {
        print(" Error to read in i2c\n");
        return 1;
    }

    *reg = inbuf[0];

	return 0;
}


uint32_t i2c_write_reg(uint32_t i2c_fd, uint8_t addr_dev, uint16_t addr_reg, uint8_t reg) {

    uint8_t outbuf[3];

    struct i2c_msg msgs[1];
    struct i2c_rdwr_ioctl_data msgset[1];

    outbuf[0] = addr_reg >> 8;
    outbuf[1] = addr_reg & 0xFF;
    outbuf[2] = reg;

    msgs[0].addr = addr_dev;
    msgs[0].flags = 0;
    msgs[0].len = 3;
    msgs[0].buf = outbuf;

    msgset[0].msgs = msgs;
    msgset[0].nmsgs = 1;

    if (ioctl(i2c_fd, I2C_RDWR, &msgset) < 0) {
        print(" Error to write in i2c \n");
        return -1;
    }
    usleep(100);
    return 0;
}
