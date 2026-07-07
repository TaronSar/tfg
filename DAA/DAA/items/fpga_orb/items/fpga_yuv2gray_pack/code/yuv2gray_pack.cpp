// Copyright (C) 2021 Xilinx, Inc
//
// SPDX-License-Identifier: BSD-3-Clause

#include "yuv2gray_pack.hpp"

void yuv2gray_pack(yuv_stream& stream_in_48, gray_stream& stream_out_32) {
#pragma HLS INTERFACE ap_ctrl_none port=return

#pragma HLS INTERFACE axis depth=24 port=stream_in_48 register
#pragma HLS INTERFACE axis depth=24 port=stream_out_32 register

	bool last = false;
	bool delayed_last = false;
	yuv2_pixel in_pixel;
	gray4_pixel out_pixel;

//	case YUV2GRAY_PACK:
		while (!delayed_last) {
#pragma HLS pipeline II=2
			bool user = false;
			ap_uint<32> data;
			for (int i = 0; i < 2; ++i) {
				if (!last) {
					stream_in_48.read(in_pixel);
					user |= in_pixel.user;
					last = in_pixel.last;
					data(i*16 + 7, i * 16) = in_pixel.data(23,16); // leo Y0
					data(i*16 + 15, i * 16 + 8) = in_pixel.data(47,40); // leo Y1
				}
			}
			if (!delayed_last) {
				out_pixel.user = user;
				out_pixel.last = last;
				out_pixel.data = data;
				stream_out_32.write(out_pixel);
			}
			delayed_last = last;
		}
//		break;

}
