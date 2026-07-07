//----------------------------------------------------------------------//
//                         BRAM                                         //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: March 2025                                                     //
//----------------------------------------------------------------------//


#ifndef BRAM_H
#define BRAM_H

#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <fcntl.h>
#include <sys/mman.h>
#include <unistd.h>

#include "dbg.h"
#include <memmap.h>

uint8_t bram_init(mem_map* mm, uint32_t memAddr, uint32_t size);
void* bram_get_ptr(mem_map mm, uint32_t offset) ;
uint8_t bram_close(mem_map mm);

#endif // BRAM_H