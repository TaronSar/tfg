#ifndef DMA_H
#define DMA_H

#include <stdio.h>
#include <stdlib.h>
#include "xil_types.h"


// ---- HW definitions ----

// ---- Register Space ----
#define DMA_MM2S_DMACR_OFFS             0x00U
#define DMA_MM2S_DMASR_OFFS             0x04U
#define DMA_MM2S_SA_OFFS                0x18U
#define DMA_MM2S_SA_MSB_OFFS            0x1CU
#define DMA_MM2S_LENGTH_OFFS            0x28U

#define DMA_S2MM_DMACR_OFFS             0x30U
#define DMA_S2MM_DMASR_OFFS             0x34U
#define DMA_S2MM_DA_OFFS                0x48U
#define DMA_S2MM_DA_MSB_OFFS            0x4CU
#define DMA_S2MM_LENGTH_OFFS            0x58U

#define DMA_CHANNEL_OFFS                0x30U

// ---- Configuration ----
#define DMA_DMACR_RS                    0x1U
#define DMA_DMACR_RESET                 0x4U

#define DMA_DMACR_IOC_IRQ_EN            0x1000U
#define DMA_DMACR_DLY_IRQ_EN            0x2000U
#define DMA_DMACR_ERR_IRQ_EN            0x4000U

#define DMA_DMASR_IDLE                  0x0002U
#define DMA_DMASR_HALT                  0x0001U

#define DMA_MIN_LENGTH                  0x100U

// ---- Scatter-Gather Register Space ----
#define XAXIDMA_BD_NDESC_OFFSET			0x00  /**< Next descriptor pointer */
#define XAXIDMA_BD_NDESC_MSB_OFFSET		0x04  /**< Next descriptor pointer */
#define XAXIDMA_BD_BUFA_OFFSET			0x08  /**< Buffer address */
#define XAXIDMA_BD_BUFA_MSB_OFFSET		0x0C  /**< Buffer address */
#define XAXIDMA_BD_MCCTL_OFFSET			0x10  /**< Multichannel Control Fields */
#define XAXIDMA_BD_STRIDE_VSIZE_OFFSET	0x14  /**< 2D Transfer Sizes */
#define XAXIDMA_BD_CTRL_LEN_OFFSET		0x18  /**< Control/buffer length */
#define XAXIDMA_BD_STS_OFFSET			0x1C  /**< Status */






// ---- IRQs ----
#define DMA_DMASR_IOC_IRQ               0x1000U
#define DMA_DMASR_DLY_IRQ               0x2000U
#define DMA_DMASR_ERR_IRQ               0x4000U

//----
#define DMA_WAIT_TRIES                  0x0U //Infinite

typedef enum {
    dma_wr,  //s2mm
    dma_rd    //mm2s
} dma_direction_t;

typedef enum {
    dma_dmacr,
    dma_dmasr,
    dma_taddr,
    dma_taddr_msb,
    dma_length
} dma_register_t;

typedef enum {
    dma_irq_int_err = 4U,
    dma_irq_slv_err = 5U,
    dma_irq_dec_err = 6U,
    dma_irq_sg_int_err = 8U,
    dma_irq_sg_slv_err = 9U,
    dma_irq_sf_dec_err = 10U,
    dma_irq_ioc = 12U,
    dma_irq_dly = 13U,
    dma_irq_err = 14U
} dma_irq_t;

typedef struct {
    dma_direction_t direction;
    int stream_2_mm;
    int mm_2_stream;
    uint64_t target_addr; // destination or source
    uint32_t length;
    uint32_t dev_base_addr;
    uint32_t irqs;
    int AddrWidth
} dma_channel_conf;

uint8_t dma_reset_core(dma_channel_conf conf);
uint8_t dma_config_channel(dma_channel_conf conf, dma_direction_t direction);
uint8_t dma_transfer_channel(dma_channel_conf conf, dma_direction_t direction);
uint8_t dma_get_irq(dma_channel_conf conf, dma_irq_t irqId);
uint8_t dma_run_channel(dma_channel_conf conf, dma_direction_t direction);
uint8_t dma_stop_channel(dma_channel_conf conf);
uint8_t dma_wait_idle(dma_channel_conf conf);
uint32_t dma_get_length(dma_channel_conf conf);


#endif // DMA_H