//
// Date      :   9 JULY 2024
// File      :   imganalysis_tb.ccp
// Author    :   Sergio Cuenca (SC)
// Contributors:
//
// Description: test bench para imganalysis IP
//
// Limitations: el WIDTH debe ser divisible entre 2
//
// Date         Version  Author  Reason for change
//
// 9 JULY 2024    1.0    SC     Created
//

#include "imganalysis.hpp"
#include <cassert>
#include <iostream>
#include <fstream>
#include "img_gray.h"

using namespace std;
#define WIDTH 10 //640 // debe ser divisible entre 2
#define HEIGHT 6 //480

#define NUMPIX WIDTH*HEIGHT

yuv_stream input_data;  // stream de paquetes yuv
yuv_stream output_data;  // stream de paquetes yuv
uint8_t sw_in[NUMPIX];  // imagen de entrada
uint32_t hw_histo[NBINS], sw_histo[NBINS];
uint32_t sw_npix, sw_sumval;
uint32_t hw_npix, hw_sumval;

int errors=0;

void sw_imganalysis(uint8_t in[NUMPIX], uint32_t hist[NBINS], uint32_t *npix, uint32_t *sumval) {
  int val;
  *sumval=0; *npix=0;
  for(int i = 0; i <NUMPIX ; i++) {
    val = in[i];
    hist[val] = hist[val] + 1;
    *sumval = *sumval+val;
    *npix = *npix + 1;
  }
}
void fill_golden(){
	//cout <<"---golden data ------------------------------------";
	//cout << endl;

	for (int r = 0; r < HEIGHT; ++r) {
		for (int c = 0; c < WIDTH; ++c){
			sw_in[r*WIDTH+c]=img_gray_6[r][c];  // img_gray_640[r][c];
			//cout << (unsigned int) sw_in[r*WIDTH+c] << " ";

		}
		//cout << endl;
	}
	//cout <<"---------------------------------------------------";
	//cout << endl;
}

void fill_stream_pix(){

	yuv2_pixel in_pixel;

	//cout <<"---stream data ------------------------------------";
	//cout << endl;
	for (int i = 0; i < HEIGHT; ++i) {
		for (int j = 0; j < WIDTH/2; ++j){

		in_pixel.user = ((i==0) & (j==0))? 1 : 0;	// Start OF Frame (SOF)
		in_pixel.last = (j==(WIDTH/2)-1)? 1 : 0;   	// End of Line (EOL)

		in_pixel.data(7,0) = 	0; 	//V0
		in_pixel.data(15,8) = 	0; 	//U0
		in_pixel.data(23,16) = img_gray_6[i][2*j]; // Y0 //img_gray_640
		in_pixel.data(31,24) = 0; 	//V1
		in_pixel.data(39,32) = 0; 	//U1
		in_pixel.data(47,40) = img_gray_6[i][2*j+1]; // Y1 //img_gray_640
		in_pixel.keep = 0xFFFFFFFFFFFFFFFF;
		input_data.write(in_pixel);

		//cout << in_pixel.data(23,16) << " ";
		//cout << in_pixel.data(47,40) << " ";
		//cout << in_pixel.last << endl;

		}
	}
	//cout <<"---------------------------------------------------";
	//cout << endl;
}


int main() {
	//uint32_t hw_histo[NBINS], sw_histo[NBINS]; // definidos aquí da un error de CSIM, se pasan a globales

    // inicializamos histogramas
	for(int i = 0; i < NBINS; i++) {
        sw_histo[i] = 0;
        hw_histo[i] = 0;
    }

	fill_golden();
	fill_stream_pix();

	sw_imganalysis(sw_in, sw_histo, &sw_npix, &sw_sumval);  // calcula golden
	//cout << "SWNumpix="<< sw_npix << " SWSumVal=" << sw_sumval << endl;

	while (!input_data.empty()){
		imganalysis(input_data, output_data, hw_histo, &hw_npix, &hw_sumval, HEIGHT, WIDTH);
	}

    yuv2_pixel output_pixel;
    int verified_pixels = 0;
    cout << "Verificando el stream de salida..." << endl;
    for (int r = 0; r < HEIGHT; ++r) {
        for (int c = 0; c < WIDTH / 2; ++c) {
            // Lee un paquete del stream de salida
            if (!output_data.empty()) {
                output_data.read(output_pixel);
                uint8_t y0 = output_pixel.data(23, 16);
                uint8_t y1 = output_pixel.data(47, 40);

                // Compara con la imagen original
                assert(y0 == sw_in[r * WIDTH + 2 * c]);
                assert(y1 == sw_in[r * WIDTH + 2 * c + 1]);

                verified_pixels += 2;
            } else {
                cout << "ERROR: El stream de salida tiene menos datos de los esperados." << endl;
                errors++;
                break;
            }
        }
        if (errors) break;
    }

    if (!errors) {
        cout << "Se han verificado " << verified_pixels << " píxeles en el stream de salida. OK." << endl;
    }

	//cout << "HWNumpix="<< hw_npix << " HwSumVal=" << hw_sumval << endl;

    /*for (int i = 0; i < NBINS; ++i) {
		if(sw_histo[i] != hw_histo[i]) {
			errors++;
			//cout << "["<< i <<"]=" << sw_histo[i] << " vs " << hw_histo[i]<< endl;
		}

	}
    cout << "ERRORES=" << errors << endl;
    cout <<"---------------------------------------------------";
    cout << endl;*/

    /*ofstream swfile, hwfile;
    swfile.open("../../../../SW_result.txt");
    hwfile.open("../../../../HW_result.txt");
    for (int i = 0; i < NBINS; i++)
    {
        swfile << sw_histo[i]<< endl;
        hwfile << hw_histo[i]<< endl;
    }*/

    for (int i = 0; i < NBINS; ++i) {
		assert(sw_histo[i] == hw_histo[i]);
	}
    assert (sw_npix == hw_npix);
    assert (sw_sumval == hw_sumval);

	return 0;
}
