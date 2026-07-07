/**
 * @file u_dma_buf.h
 * @brief Library for U-DMA-BUF
 * 
 * @date 	February, 2024
 * @author	Victor Morales, Sergio Cuenca
 * @company Embention
 */

#ifndef U_DMA_BUF_H
#define U_DMA_BUF_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <unistd.h>
#include <fcntl.h>
#include <sys/mman.h>

#include "dbg.h"

//#define MODULE_PATH "/lib/modules/5.4.0*/extra/u-dma-buf.ko";
#define MODULE_PATH "/lib/modules/6.1.30*/extra/u-dma-buf.ko"

typedef struct {
    uint8_t id;
    uint64_t phys_addr;
    void* virt_addr;
    uint32_t size;
} u_dma_buf;

uint8_t u_dma_buf_setup(u_dma_buf* buffer, uint8_t id, uint32_t size);
uint64_t u_dma_buf_get_physical_addr(u_dma_buf buffer, uint32_t offset);
uint32_t u_dma_buf_get_size(u_dma_buf buffer);
void* u_dma_buf_get_virtual_space(u_dma_buf buffer, uint32_t offset, uint32_t size);
//void set_dma_buff_path(const char* dma_buff);

#endif // U_DMA_BUF_H