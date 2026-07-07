//----------------------------------------------------------------------//
//                         IMX219 Linux Driver                          //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//



#ifndef IMX219_H
#define IMX219_H

#include <stdio.h>
#include <stdlib.h>

#include "dbg.h"
#include "i2c.h"

#define I2C_DEVICE_NUM      3U // ----> i2c-3 is attached to channel 0
#define I2C_DEVICE_ADDR     0x10U
#define IMX219_ID           0x0219U

// IMX219 DEFINED REGISTERS
#define IMX219_MODEL_ID_H   0x0000U
#define IMX219_MODEL_ID_L   0x0001U






uint8_t imx219_init();
uint8_t imx219_config();

#endif // IMX219_H