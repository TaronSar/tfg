//----------------------------------------------------------------------//
//                       Image file generator                           //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//


#ifndef IMG_H
#define IMG_H

#include <stdio.h>
#include <stdlib.h>
#include <inttypes.h>
#include <fcntl.h>

#include "dbg.h"

uint8_t img_create_raw10(const char* fname, uint32_t *frame, uint32_t imgW,uint32_t imgH);
uint8_t img_create_raw10_2pxclk(const char* fname, uint64_t frame[], uint32_t imgW,uint32_t imgH);
uint8_t img_create_raw8_2pxclk(const char* fname, uint64_t frame[], uint32_t imgW,uint32_t imgH);
uint8_t img_create_gray8_2pxclk(const char* fname, uint64_t frame[], uint32_t imgW,uint32_t imgH);
uint8_t img_create_gray8(const char* fname, uint8_t *frame, uint32_t imgW,uint32_t imgH);

uint8_t img_create_gray8_kp(const char* fname, uint8_t* frame, uint32_t* kp_area, uint32_t kp_size, uint32_t imgW,uint32_t imgH);

#endif // IMG_H