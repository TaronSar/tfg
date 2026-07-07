/**
 * @file pixel_pack.c
 * @brief Library for pixel pack IP from PYNQ.
 * 
 * @date 	February, 2024
 * @author	Victor Morales, Sergio Cuenca
 * @company Embention
 */

#ifndef PIXEL_PACK_H
#define PIXEL_PACK_H

#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>

#include "dbg.h"

#include "memmap.h"

typedef enum {
    pixel_pack_mode_v24 = 0,
    pixel_pack_mode_v32 = 1,
    pixel_pack_mode_v8 = 2,
    pixel_pack_mode_v16 = 3,
    pixel_pack_mode_v16C = 4
} pixel_pack_mode_t;


typedef struct {
    uint32_t dev_base_addr;
    pixel_pack_mode_t mode;
} pixel_pack_conf;


uint8_t pixel_pack_setup(pixel_pack_conf config);

#endif // PIXEL_PACK_H