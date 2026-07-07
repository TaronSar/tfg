//
// Date      :   9 JULY 2024
// File      :   imganalysis.ccp
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


#include "imganalysis.hpp"
using namespace std;
//#define DEBUG

void imganalysis(yuv_stream& stream_in_48, yuv_stream& stream_out_48, uint32_t histo[NBINS], uint32_t *npix, uint32_t *sumval,  uint32_t rows, uint32_t cols) {
//#pragma HLS INTERFACE s_axilite port=return bundle=control
#pragma HLS INTERFACE ap_ctrl_none port=return
#pragma HLS INTERFACE s_axilite port=rows bundle=histo_data
#pragma HLS INTERFACE s_axilite port=cols bundle=histo_data
#pragma HLS INTERFACE s_axilite port=histo bundle=histo_data
#pragma HLS INTERFACE s_axilite port=npix bundle=histo_data
#pragma HLS INTERFACE s_axilite port=sumval bundle=histo_data

#pragma HLS INTERFACE axis depth=24 port=stream_in_48 register
#pragma HLS INTERFACE axis depth=24 port=stream_out_48 register

#pragma HLS STABLE variable= rows
#pragma HLS STABLE variable= cols

	bool last_pack = false;
	yuv2_pixel in_pixel;

/* Recomendación: Xilinx recommends specifying arrays that are to be
implemented as memories with the static qualifier. This not only ensures that Vitis HLS implements the
array with a memory in the RTL; it also allows the default initialization behavior of the static types to be
used.*/
	static uint32_t histA[NBINS];   // con static los arrays se inicializan en el bitstream
	static uint32_t histB[NBINS];
	uint8_t valA, valB;
	uint8_t oldA = 0;
	uint8_t oldB = 0;
	uint32_t accA = 0;
	uint32_t accB = 0;
	uint32_t SumValA=0;
	uint32_t SumValB=0;
	uint32_t NumPix=0;
	uint32_t FirstPix=0;
	uint32_t NumLines=0;

	Init: for(int i = 0; i < NBINS; i++) {
	#pragma HLS PIPELINE II=1
	        histA[i] = 0;
	        histB[i] = 0;
	}

#pragma HLS DEPENDENCE variable=histA intra RAW false
#pragma HLS DEPENDENCE variable=histB intra RAW false

	//hist_rows:for (int i=0; i< rows; ++i){
	//	hist_cols: for (int j=0; j< cols/2; ++j){
	histo_loop: for (int i=0; i< rows*cols/2; ++i){
		#pragma HLS pipeline II=1
			stream_in_48.read(in_pixel);
			stream_out_48.write(in_pixel);

			last_pack = in_pixel.last;

			valA = in_pixel.data(23,16); // leo Y0
			valB = in_pixel.data(47,40); // leo Y1

			SumValA += valA;
			SumValB += valB;
			NumPix +=2;

			#ifdef DEBUG
				cout << "valA="<<(unsigned int) valA << " / valB="<<(unsigned int) valB << endl;
				cout << "oldA="<<(unsigned int) oldA << " / oldB="<<(unsigned int) oldB << endl;
			#endif
		    // histA
			if(oldA == valA) {
				accA = accA + 1;
			} else {
				histA[oldA] = accA;
				accA = histA[valA] + 1;
			}

			// histB
			if(oldB == valB) {
				accB = accB + 1;
			} else {
				histB[oldB] = accB;
				accB = histB[valB] + 1;
			}

			#ifdef DEBUG
				cout << "accA=" << accA << " / accB=" << accB<< endl;
				cout << "hA["<<(unsigned int) oldA<<"]="<< histA[oldA] << " / hB["<<(unsigned int)oldB<<"]="<< histB[oldB]  << endl;
				cout <<"---------------------------------------------------"<<endl;
			#endif

		    // update vals
			oldA = valA;
			oldB = valB;
		//}//end cols
	}//end rows

	histA[oldA] = accA;
	histB[oldB] = accB;
	#ifdef DEBUG
		cout << histA[oldA] << " "<< histB[oldB]  << endl;

		cout << SumValA << " "<< SumValB << " "<< NumPix  << endl;
	#endif

	hist_Reduce_Clear:  // Una vez que han llegado todos los pixels se calcula el histograma y se inicializan los histparciales
		// set bit_busy
	for(int i = 0; i < NBINS; i++) {
	#pragma HLS PIPELINE II=1
			histo[i] = histA[i] + histB[i];
			histA[i]=0;
			histB[i]=0;

	}

	*sumval = SumValA + SumValB;
	*npix = NumPix;
	SumValA=0; SumValB=0; NumPix=0;
    // clear bit_busy
}



