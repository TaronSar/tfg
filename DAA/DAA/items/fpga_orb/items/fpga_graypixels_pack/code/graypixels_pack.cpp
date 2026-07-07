// 
// SC: empaqueta dos bloques de 4pixels gray en un bloque de 8pixels gray 
// 20240315

#include "graypixels_pack.hpp"

void graypixels_pack(gray4_stream& stream_in_32, gray8_stream& stream_out_64) {
#pragma HLS INTERFACE ap_ctrl_none port=return

#pragma HLS INTERFACE axis depth=24 port=stream_in_32 register
#pragma HLS INTERFACE axis depth=24 port=stream_out_64 register

	bool last = false;
	bool delayed_last = false;
	gray4_pixel in_pixel;
	gray8_pixel out_pixel;

//	case GRAY2GRAY:
		while (!delayed_last) {
#pragma HLS pipeline II=2
			delayed_last = last;
			bool user = false;
			ap_uint<64> data;
			for (int i = 0; i < 2; ++i) {
				if (!last) {
					stream_in_32.read(in_pixel);
					user |= in_pixel.user;
					last = in_pixel.last;
					data(i*32 + 31, i * 32) = in_pixel.data(31,0); // leo Y3Y2Y1Y0
				}
			}
			if (!delayed_last) {
				out_pixel.user = user;
				out_pixel.last = last;
				out_pixel.data = data;
				stream_out_64.write(out_pixel);
			}
		}
//		break;

}
