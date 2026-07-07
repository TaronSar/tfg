//----------------------------------------------------------------------//
//                         I2C Linux Driver                             //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//


#ifndef I2C_H
#define I2C_H

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <fcntl.h>
#include <inttypes.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>

#include "dbg.h"

uint32_t i2c_init(uint32_t *i2c_fd, uint8_t sel_i2c);
uint32_t i2c_read_reg(uint32_t i2c_fd, uint8_t addr_dev, uint16_t addr_reg, uint8_t *reg);
uint32_t i2c_write_reg(uint32_t i2c_fd, uint8_t addr_dev, uint16_t addr_reg, uint8_t reg);

#endif // I2C_H