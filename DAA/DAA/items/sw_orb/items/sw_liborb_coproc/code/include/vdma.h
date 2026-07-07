//----------------------------------------------------------------------//
//                         VDMA Linux Driver                          //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//



#ifndef VDMA_H
#define VDMA_H

#include <stdio.h>
#include <stdlib.h>

#include "dbg.h"

#include "memmap.h"

#define VDMA_PX_WIDTH                   0x1U //bytes
// ---- HW definitions ----
#define VDMA_MAX_FRAME_BUFF                  1U // CHANGE ACCORDING VIVADO PROJECT

// ---- Register Space ----
#define VDMA_MM2S_VDMACR_OFFS           0x00U
#define VDMA_MM2S_VDMASR_OFFS           0x04U
#define VDMA_MM2S_PARK_PTR_OFFS         0x28U

#define VDMA_MM2S_START_ADDR            0x5CU

#define VDMA_MM2S_HSIZE_OFFS            0x54U
#define VDMA_MM2S_VSIZE_OFFS            0x50U                 

#define VDMA_MM2S_FRMDLY_STRIDE_OFFS    0x58U

#define VDMA_S2MM_VDMACR_OFFS           0x30U
#define VDMA_S2MM_VDMASR_OFFS           0x34U

#define VDMA_S2MM_START_ADDR            0xACU

#define VDMA_S2MM_HSIZE_OFFS            0xA4U
#define VDMA_S2MM_VSIZE_OFFS            0xA0U                 

#define VDMA_S2MM_FRMDLY_STRIDE_OFFS    0xA8U



#define VDMA_SRT_ADDR_OFFS              0x04U
#define VDMA_CHANNEL_OFFS               0x30U
#define VDMA_CHANNEL_OFFS_B             0x50U
// ---- Configuration ----

#define VDMA_VDMACR_RS                  0x1U
#define VDMA_VDMACR_CIRCPRK             0x2U
#define VDMA_VDMACR_RESET               0x4U
#define VDMA_VDMACR_FCNTEN              0x10U
#define VDMA_VDMACR_FCNTIRQEN           0x1000U

#define VDMA_VDMACR_FRMCNT_OFFS         16U

#define VDMA_VDMACR_CONF                VDMA_VDMACR_CIRCPRK | VDMA_VDMACR_FCNTEN | VDMA_VDMACR_FCNTIRQEN

// ---- IRQs ----       
#define VDMA_VDMASR_FRMCNT_IRQ          12U

typedef enum {
    vdma_wr,  //s2mm
    vdma_rd    //mm2s
} vdma_direction_t;

typedef enum {
    vdmaIntErr = 4U,  //s2mm
    vdmaSlvErr = 5U,
    vdmaDecErr = 6U,
    sofEarlyErr = 7U,
    eolEarlyErr = 8U,
    sofLateErr = 11U,
    frmCntIrq = 12U,
    dlyCntIrq = 13U,
    errIrq = 14U,
    eolLateErr = 15U   //mm2s
} vdma_irq_t;



typedef enum {
    vdma_vdmacr, 
    vdma_vdmasr, 
    vdma_str_addr,
    vdma_h_size, 
    vdma_v_size,
    vdma_frm_dly_str    
} vdma_register_t;

typedef struct {
    uint32_t dev_base_addr;
    vdma_direction_t direction;
    uint32_t vdmacr;
    uint32_t start_addrs[VDMA_MAX_FRAME_BUFF];
    uint32_t n_frame_buff;
    uint32_t h_size;
    uint32_t v_size;
} vdma_channel_conf;


uint8_t vdma_reset_channel(vdma_channel_conf conf);
uint8_t vdma_config_channel(vdma_channel_conf conf);
uint8_t vdma_get_irq(vdma_channel_conf conf, vdma_irq_t irqId);
uint8_t vdma_update_frame_addr(vdma_channel_conf conf, uint32_t fAddr);
uint8_t vdma_run_channel(vdma_channel_conf conf);

#endif // VDMA_H