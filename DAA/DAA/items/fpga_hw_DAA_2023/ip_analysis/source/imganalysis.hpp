//
// Date      :   9 JULY 2024
// File      :   imganalysis.hpp
// Author    :   Sergio Cuenca (SC)
// Contributors:
//
// Description: lee los pixels de un stream de video (2pixels per clock: Y1U1V1_Y0U0V0) y calcula
// las estadísticas de la imagen:
//  - uint32 hist[256]
//  - SumVal, NumPix, ...
// Xilinx Video AxiStream protocol
// 	- Start Of Frame (SOF): stream.user
//	- End Of Line (EOL): stream.last
//
// References:  https://github.com/KastnerRG/pp4fpgas
//
// Limitations: el WIDTH debe ser divisible entre 2
//
// Date         Version  Author  Reason for change
//
// 9 JULY 2024    1.0    SC     Created
//

#include <ap_fixed.h>
#include <ap_int.h>
#include "hls_stream.h"
#include <ap_axi_sdata.h>

#define NBINS 256

typedef unsigned int uint32_t;
typedef unsigned char uint8_t;
typedef ap_axiu<48,1,0,0> yuv2_pixel;  // Y1U1V1_Y0U0V0


typedef hls::stream<yuv2_pixel> yuv_stream;

void imganalysis(yuv_stream& stream_in_48, yuv_stream& stream_out_48, uint32_t histo[NBINS], uint32_t *npix, uint32_t *sumval, uint32_t rows, uint32_t cols ) ;   // versión 2.0
