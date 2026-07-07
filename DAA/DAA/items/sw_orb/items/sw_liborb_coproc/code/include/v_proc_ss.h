/**
 * @file v_proc_ss.c
 * @brief Library for video processing subsystem of Xilinx.
 * 
 * @date 	February, 2024
 * @author	Victor Morales, Sergio Cuenca
 * @company Embention
 */

#ifndef V_PROC_SS_H
#define V_PROC_SS_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#include "dbg.h"

#include "memmap.h"

#define V_PROC_SS_CTRL_OFFS         0x00U
#define V_PROC_SS_IN_V_FRT_OFFS     0x10U
#define V_PROC_SS_OUT_V_FRT_OFFS    0x18U
#define V_PROC_SS_WIDTH_OFFS        0x20U
#define V_PROC_SS_HEIGHT_OFFS       0x28U

#define V_PROC_SS_COEFF_K11_OFFS    0x50U
#define V_PROC_SS_COEFF_K12_OFFS    0x58U
#define V_PROC_SS_COEFF_K13_OFFS    0x60U
#define V_PROC_SS_COEFF_K21_OFFS    0x68U
#define V_PROC_SS_COEFF_K22_OFFS    0x70U
#define V_PROC_SS_COEFF_K23_OFFS    0x78U
#define V_PROC_SS_COEFF_K31_OFFS    0x80U
#define V_PROC_SS_COEFF_K32_OFFS    0x88U
#define V_PROC_SS_COEFF_K33_OFFS    0x90U
#define V_PROC_SS_COEFF_R_OFFS_OFFS 0x98U
#define V_PROC_SS_COEFF_G_OFFS_OFFS 0xA0U
#define V_PROC_SS_COEFF_B_OFFS_OFFS 0xA8U

#define V_PROC_SS_CLAMP_MIN_OFFS    0xB0U
#define V_PROC_SS_CLIP_MAX_OFFS     0xB8U

#define V_PROC_SS_CTRL_START_BIT    0x01U
#define V_PROC_SS_CTRL_DONE_BIT     0x02U
#define V_PROC_SS_CTRL_IDLE_BIT     0x04U
#define V_PROC_SS_CTRL_READY_BIT    0x08U
#define V_PROC_SS_CTRL_AUTO_RST_BIT 0x80U

typedef struct {
    uint32_t dev_base_addr;
    uint32_t width;
    uint32_t height;
    uint32_t data_width;
} v_proc_ss_conf;


uint8_t v_proc_ss_setup(v_proc_ss_conf config);

#endif // V_PROC_SS_H