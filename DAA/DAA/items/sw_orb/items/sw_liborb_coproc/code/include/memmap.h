//----------------------------------------------------------------------//
//                         MEMMAP                                         //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//


#ifndef MEMMAP_H
#define MEMMAP_H

#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include "dbg.h"

#ifdef MEMMAP_VERBOSE
#define mmap_print(f_, ...) printf((f_), ##__VA_ARGS__)
#else
#define mmap_print(f_, ...) 
#endif

#define MAP_SIZE 0x10000U // from 0U to 0xFFFFU
#define MAP_MASK (MAP_SIZE - 1)

typedef struct 
{
    void *mapped_base;
    uint32_t memoryBase;
}mem_map;


uint8_t memmap_init(mem_map* mm, uint32_t memAddr);

uint8_t memmap_write(mem_map mm,  uint32_t addr_reg, uint32_t reg);

uint8_t memmap_read(mem_map mm, uint32_t addr_reg, uint32_t *reg);

uint8_t memmap_write_byte(mem_map mm, uint32_t addr_reg, char reg);

uint8_t memmap_close(mem_map mm);

#endif // MEMMAP_H