/**
 * @file imx296.h
 * @brief Library for IMX296LQR-C sensor.
 * 
 * @date 	January, 2024
 * @author	Victor Morales
 * @company Embention
 */

#ifndef IMX296_H
#define IMX296_H

#include <stdio.h>
#include <stdlib.h>

#include "dbg.h"
#include "i2c.h"

#define I2C_DEVICE_NUM      2U // ----> i2c-2 is attached to the PL IIC
#define I2C_DEVICE_ADDR     0x1AU
#define IMX296LQ_ID         0x4AU // IMX296_SENSOR_INFO_IMX296LQ --> https://github.com/raspberrypi/linux/blob/rpi-6.1.y/drivers/media/i2c/imx296.c#L1038
//
#define IMX296_BAYER_PHASE         0x00U // IMX296LQR-C Dataseet p.22 coded according Xilinx IP Demosaic
// IMX219 DEFINED REGISTERS
#define IMX296_INFO_TYPE_ADDR   0x3149U

#define IMX296_FID0_ROI_ADDR        0x3300U
#define IMX296_MIPIC_AREA3W_ADDR    0x4182U

#define IMX296_FID0_ROI_ADDR        0x3300U        
#define IMX296_FID0_ROIPH1_ADDR     0x3310U
#define IMX296_FID0_ROIPV1_ADDR     0x3312U
#define IMX296_FID0_ROIWH1_ADDR     0x3314U
#define IMX296_FID0_ROIWV1_ADDR     0x3316U

#define IMX296_HMAX_ADDR            0x3014U
#define IMX296_VMAX_ADDR            0x3010U

#define IMX296_INCKSEL_BASE_ADDR    0x3089U
#define IMX296_GTTABLENUM_ADDR      0x4114U
#define IMX296_CTRL418C_ADDR        0x418CU

#define IMX296_GAINDLY_ADDR         0x3212U
#define IMX296_GAIN_ADDR            0x3204U
#define IMX296_BLKLEVEL_ADDR        0x3254U


#define IMX296_CTRL00_ADDR          0x3000U
#define IMX296_CTRL0A_ADDR          0x300AU
#define IMX296_CTRL0B_ADDR          0x300BU
#define IMX296_CTRL0D_ADDR          0x300DU
#define IMX296_LOWLAGTRG_ADDR       0x30AEU


#define IMX296_SHS_0                0x308DU
#define IMX296_SHS_1                0x308EU   
#define IMX296_SHS_2                0x308FU   

#define IMX296_MIN_SHS              4U  

#define IMX296_MAX_GAIN             512U
#define IMX296_MAX_SHS              1117U
#define IMX296_MAX_HEIGHT           1088U
#define IMX296_MAX_WIDTH            1456U   

typedef struct {
    uint16_t width;
    uint16_t height;
    uint16_t crop_top;
    uint16_t crop_left;
    uint16_t bayer_phase;
    uint32_t shs;
    uint16_t gain;
} imx296_conf;


uint8_t imx296_setup(imx296_conf config);
void imx296_set_shs(uint32_t shs);
void imx296_set_blklevel(uint16_t blklevel);
void imx296_set_gain(uint16_t gain);

#endif // IMX296_H