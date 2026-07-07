// 
// SC: empaqueta los Y de 2 pixels YUV en un paquete de 4 pixels gray
// Y1U1V1_Y0U0V0 => Y3Y2Y1Y0
// 20240315

#include <ap_fixed.h>
#include <ap_int.h>
#include "hls_stream.h"
#include <ap_axi_sdata.h>

typedef ap_axiu<48,1,1,1> yuv2_pixel;  // Y1U1V1_Y0U0V0
typedef ap_axiu<32,1,1,1> gray4_pixel; // Y3Y2Y1Y0

typedef hls::stream<yuv2_pixel> yuv_stream;
typedef hls::stream<gray4_pixel> gray_stream;

void yuv2gray_pack(yuv_stream& stream_in_48, gray_stream& stream_out_32);
