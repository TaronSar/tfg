// 
// SC: empaqueta dos bloques de 4pixels gray en un bloque de 8pixels gray 
// 20240315

#include <ap_fixed.h>
#include <ap_int.h>
#include "hls_stream.h"
#include <ap_axi_sdata.h>

typedef ap_axiu<32,1,1,1> gray4_pixel;  // Y3Y2Y1Y0
typedef ap_axiu<64,1,1,1> gray8_pixel; // Y7Y6Y5Y4_Y3Y2Y1Y0

typedef hls::stream<gray4_pixel> gray4_stream;
typedef hls::stream<gray8_pixel> gray8_stream;

void graypixels_pack(gray4_stream& stream_in_32, gray8_stream& stream_out_64);
