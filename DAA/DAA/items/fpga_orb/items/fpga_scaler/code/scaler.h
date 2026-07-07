/**
* This file is part of ac^2SLAM.
*
* Copyright (C) 2021 Cheng Wang <wangcheng at stu dot xjtu dot edu dot cn> (Xi'an Jiaotong University)
* For more information see <https://github.com/SLAM-Hardware/acSLAM>
*
* ac^2SLAM is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* ac^2SLAM is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with ac^2SLAM. If not, see <http://www.gnu.org/licenses/>.
*/

/***************************************************************************
Change the Parallelism
1. Change INPUT_PIXEL_NUM to 4n (n=1,2,3...).
2. Change ARRAY_PARTITION and UNROLL factor in resize.cpp. 
   The factor is equal to INPUT_PIXEL_NUM/4.
 ***************************************************************************/

#ifndef SCALERN_H
#define SCALERN_H

//#define DEBUG
#define AXILITE

#include <iostream>
#include "hls_stream.h"
#include "ap_int.h"
#include "hls_math.h"
#include "ap_fixed.h"
#include "ap_axi_sdata.h"

#define SCALE  2.25  //3.5 // SC: solo se utiliza en tb
#define PIXEL_BIT 8
#define INPUT_BIT INPUT_PIXEL_NUM * PIXEL_BIT
#define INPUT_PIXEL_NUM 4 //16
#define OUTPUT_BIT OUTPUT_PIXEL_NUM * PIXEL_BIT
#define OUTPUT_PIXEL_NUM 4
#define WIDTH 1440 //1241
#define HEIGHT 1080 //376
#define WIN_SZ 2
#define WIDTH_BIT 11
#define HEIGHT_BIT 11 //9
#define WIN_SZ_BIT 2
#define PIXEL_NUM_BIT WIDTH_BIT + HEIGHT_BIT
#define MAX_PIXEL_VAL 255
#define PROCESS_NUM INPUT_PIXEL_NUM
#define PROCESS_BIT PROCESS_NUM * PIXEL_BIT
#define MERGE_NUM 4
#define WIDTH_AFTER_MERGE 360  //311 // ceil(WIDTH / MERGE_NUM)
#define LOG_2_MERGE_NUM 3  //SC: revisar
#define INPUT_STREAM_BIT INPUT_BIT
#define OUTPUT_STREAM_BIT OUTPUT_BIT
//const ap_ufixed<64, 2> inv_scale_64 = 1 / 1.2;

#ifdef AXILITE
	void scaler(hls::stream<ap_axiu<INPUT_STREAM_BIT, 1, 1, 1> > &srcStream, hls::stream<ap_axiu<OUTPUT_STREAM_BIT, 1, 1, 1> > &outStream, ap_uint<32> p_width, ap_uint<32> p_height, ap_uint<32> p_scale, ap_uint<32> p_inv_scale);
#else
	void scaler(hls::stream<ap_axiu<32, 1, 1, 1> > &cfgStream, hls::stream<ap_axiu<INPUT_STREAM_BIT, 1, 1, 1> > &srcStream, hls::stream<ap_axiu<32, 1, 1, 1> > &cfgoutStream, hls::stream<ap_axiu<OUTPUT_STREAM_BIT, 1, 1, 1> > &outStream);
#endif

template <class T, int W, int I>
T my_round(T x)
{
    T tmp = x;
    if (x.range(W - I - 1, W - I - 1) == 1)
        tmp.range(W - 1, W - I) = tmp.range(W - 1, W - I) + 1;
    tmp.range(W - I - 1, 0) = 0;
    return tmp;
}

template <class T, int W, int I>
T my_ceil(T x)
{
    T tmp = x;
    if (x.range(W - I - 1, 0) != 0)
        tmp.range(W - 1, W - I) = tmp.range(W - 1, W - I) + 1;
    tmp.range(W - I - 1, 0) = 0;
    return tmp;
}

template <class T, int W, int I>
T my_floor(T x)
{
    T tmp = x;
    tmp.range(W - I - 1, 0) = 0;
    return tmp;
}

#endif
