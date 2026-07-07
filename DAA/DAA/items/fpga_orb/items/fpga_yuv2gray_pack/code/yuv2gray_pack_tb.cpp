// Copyright (C) 2021 Xilinx, Inc
//
// SPDX-License-Identifier: BSD-3-Clause

// SC: empaqueta los Y de 2 pixels YUV en un paquete de 4 pixels gray
// Y1U1V1_Y0U0V0 => Y3Y2Y1Y0

#include "yuv2gray_pack.hpp"
#include <cassert>
#include <iostream>
using namespace std;

yuv_stream input_data;
gray_stream output_data;

void fill_stream(){
	for (int i = 0; i < 24; ++i) {
		yuv2_pixel in_pixel;
		in_pixel.user = (i==0)? 1 : 0;
		in_pixel.last = (i==23)? 1 : 0;

		in_pixel.data(7,0) = 	0; 	//6 * i;
		in_pixel.data(15,8) = 	0; 	//6 * i + 1;
		in_pixel.data(23,16) = 2*i; 	//6 * i + 2;
		in_pixel.data(31,24) = 0; 	//6 * i + 3;
		in_pixel.data(39,32) = 0; 	//6 * i + 4;
		in_pixel.data(47,40) = 2*i+1; //6 * i + 5;
		input_data.write(in_pixel);
		/*cout << in_pixel.data(7,0) << " ";
		cout << in_pixel.data(15,8) << " ";
		cout << in_pixel.data(23,16) << " ";
		cout << in_pixel.data(31,24) << " ";
		cout << in_pixel.data(39,32) << " ";
		cout << in_pixel.data(47,40) << endl;
		cout <<"---------------------------------------------------";
		cout << endl;*/
	}
}

int main() {

	fill_stream();
	while (!input_data.empty())
		yuv2gray_pack(input_data, output_data); 	// lee 24 paquetes 2yuv devuelve 12 paquetes 4gray
																	// Y1U1V1_Y0U0V0 => Y3Y2Y1Y0
	
	for (int i = 0; i < 12; ++i) {
		gray4_pixel out_pixel = output_data.read();
		assert(out_pixel.user == (i == 0? 1: 0));
		assert(out_pixel.last == (i == 11? 1: 0));
		assert(out_pixel.data(7,0) == i*4);
		assert(out_pixel.data(15,8) == i*4 + 1);
		assert(out_pixel.data(23,16) == i*4 + 2);
		assert(out_pixel.data(31,24) == i*4 + 3);
		/*cout << out_pixel.data(7,0) << " ";
		cout << out_pixel.data(15,8) << " ";
		cout << out_pixel.data(23,16) << " ";
		cout << out_pixel.data(31,24) << " ";*/
	}


	return 0;
}
