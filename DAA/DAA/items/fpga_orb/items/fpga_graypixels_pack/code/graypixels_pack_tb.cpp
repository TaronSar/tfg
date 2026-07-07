// Copyright (C) 2021 Xilinx, Inc
//
// SPDX-License-Identifier: BSD-3-Clause

// SC: empaqueta dos bloques de 4pixels gray en un bloque de 8pixels gray 
// 20240315

#include "graypixels_pack.hpp"
#include <cassert>
#include <iostream>
using namespace std;

gray4_stream input_data;
gray8_stream output_data;

void fill_stream(){
	for (int i = 0; i < 24; ++i) {
		gray4_pixel in_pixel;
		in_pixel.user = (i==0)? 1 : 0;
		in_pixel.last = (i==23)? 1 : 0;

		in_pixel.data(7,0) = 	4*i; 	
		in_pixel.data(15,8) = 4*i +1; 	
		in_pixel.data(23,16) = 4*i+2; 	
		in_pixel.data(31,24) = 4*i+3; 	

		input_data.write(in_pixel);
		/*cout << in_pixel.data(7,0) << " ";
		cout << in_pixel.data(15,8) << " ";
		cout << in_pixel.data(23,16) << " ";
		cout << in_pixel.data(31,24) << " ";
		cout <<  endl;
		cout <<"---------------------------------------------------";
		cout << endl;*/
	}
}

int main() {

	fill_stream();
	while (!input_data.empty())
		graypixels_pack(input_data, output_data); 	// lee 24 paquetes gray4 (32b) devuelve 12 paquetes gray8 (64)
																	
	
	for (int i = 0; i < 12; ++i) {
		gray8_pixel out_pixel = output_data.read();
		assert(out_pixel.user == (i == 0? 1: 0));
		assert(out_pixel.last == (i == 11? 1: 0));
		assert(out_pixel.data(7,0) == i*6);
		assert(out_pixel.data(15,8) == i*6 + 1);
		assert(out_pixel.data(23,16) == i*6 + 2);
		assert(out_pixel.data(31,24) == i*6 + 3);
		assert(out_pixel.data(39,32) == i*6 + 4);
		assert(out_pixel.data(47,40) == i*6 + 5);
		assert(out_pixel.data(55,48) == i*6 + 6);
		assert(out_pixel.data(63,56) == i*6 + 7);

		/*cout << out_pixel.data(7,0) << " ";
		cout << out_pixel.data(15,8) << " ";
		cout << out_pixel.data(23,16) << " ";
		cout << out_pixel.data(31,24) << " ";*/
	}


	return 0;
}
