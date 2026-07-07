//----------------------------------------------------------------------//
//                       Image file generator                           //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//



#include "img.h"


uint8_t img_create_raw10(const char* fname, uint32_t frame[], uint32_t imgW,uint32_t imgH){

    uint32_t i, a_Ch, b_Ch, c_Ch, greyS;


    FILE *file = fopen(fname, "w");

	if (file == NULL) {
        print("File can't be opened\n");
        return 1; 
    }

	fprintf(file, "P3\n%d %d\n1023\n",imgW, imgH);
		
	for(i = 0; i < imgW*imgH; i++){
		a_Ch = ((frame[i]) & 0x3FFU);
		b_Ch = ((frame[i] >> 10) & 0x3FFU);
		c_Ch = ((frame[i] >> 20) & 0x3FFU);

		greyS = (a_Ch + b_Ch + c_Ch) / 3;

    	fprintf(file, "%u %u %u ", greyS, greyS , greyS);
		if((i % imgW) == 0 && i != 0){
			fprintf(file, "\n");
		}
	}
	
    fclose(file);
    print("Created picture file --> %s\n", fname);



	return 0;
}


uint8_t img_create_raw10_2pxclk(const char* fname, uint64_t frame[], uint32_t imgW,uint32_t imgH){

    uint32_t i, a_Ch, b_Ch, c_Ch, a_Ch2, b_Ch2, c_Ch2, greyS, greyS2;


    FILE *file = fopen(fname, "w");

	if (file == NULL) {
        print("File can't be opened\n");
        return 1; 
    }

	fprintf(file, "P3\n%d %d\n1023\n",imgW, imgH);
		
	for(i = 0; i < imgW*imgH/2; i++){
		a_Ch = ((frame[i]) & 0x3FFU);
		b_Ch = ((frame[i] >> 10) & 0x3FFU);
		c_Ch = ((frame[i] >> 20) & 0x3FFU);
		a_Ch2 = ((frame[i] >> 30) & 0x3FFU);
		b_Ch2 = ((frame[i] >> 40) & 0x3FFU);
		c_Ch2 = ((frame[i] >> 50) & 0x3FFU);

		greyS = (a_Ch + b_Ch + c_Ch) / 3;
		greyS2 = (a_Ch2 + b_Ch2 + c_Ch2) / 3;

    	fprintf(file, "%u %u %u ", greyS, greyS , greyS);
    	fprintf(file, "%u %u %u ", greyS2, greyS2 , greyS2);
		if((i % imgW/2) == 0 && i != 0){
			fprintf(file, "\n");
		}
	}
	
    fclose(file);
    print("Created picture file --> %s\n", fname);



	return 0;
}


uint8_t img_create_raw8_2pxclk(const char* fname, uint64_t frame[], uint32_t imgW,uint32_t imgH){

    uint32_t i; 
	uint8_t a_Ch, b_Ch, c_Ch, a_Ch2, b_Ch2, c_Ch2, greyS, greyS2;


    FILE *file = fopen(fname, "w");

	if (file == NULL) {
        print("File can't be opened\n");
        return 1; 
    }

	fprintf(file, "P3\n%d %d\n1023\n",imgW, imgH);
		
	for(i = 0; i < imgW*imgH/2; i++){
		a_Ch = ((frame[i]) & 0xFFU);
		b_Ch = ((frame[i] >> 8) & 0xFFU);
		c_Ch = ((frame[i] >> 16) & 0xFFU);
		a_Ch2 = ((frame[i] >> 24) & 0xFFU);
		b_Ch2 = ((frame[i] >> 32) & 0xFFU);
		c_Ch2 = ((frame[i] >> 40) & 0xFFU);


		greyS = (a_Ch + b_Ch + c_Ch) / 3;
		greyS2 = (a_Ch2 + b_Ch2 + c_Ch2) / 3;

    	fprintf(file, "%u %u %u ", greyS, greyS , greyS);
    	fprintf(file, "%u %u %u ", greyS2, greyS2 , greyS2);
		if((i % imgW/2) == 0 && i != 0){
			fprintf(file, "\n");
		}
	}
	
    fclose(file);
    print("Created picture file --> %s\n", fname);



	return 0;
}

uint8_t img_create_gray8_2pxclk(const char* fname, uint64_t frame[], uint32_t imgW,uint32_t imgH){

    uint32_t i;

	uint8_t *newFrame = (uint8_t *)frame;

    FILE *file = fopen(fname, "w");

	if (file == NULL) {
        print("File can't be opened\n");
        return 1; 
    }
	uint8_t highNumber = 0;
	fprintf(file, "P3\n%d %d\n255\n",imgW, imgH);
	for(i = 0; i < imgW*imgH; i++){                                                
			
			if(newFrame[i] > highNumber) highNumber = newFrame[i];
    		fprintf(file, "%d %d %d ", newFrame[i], newFrame[i] , newFrame[i]);

		if((i % imgW) == 0 && i != 0){
			fprintf(file, "\n");
		}
	}
	
    print("Higher --> %d\n", highNumber);
    fclose(file);
    print("Created picture file --> %s\n", fname);



	return 0;
}

uint8_t img_create_gray8(const char* fname, uint8_t* frame, uint32_t imgW,uint32_t imgH){

    uint32_t i, greyS;

    FILE *file = fopen(fname, "w");

	if (file == NULL) {
        print("File can't be opened\n");
        return 1; 
    }

	fprintf(file, "P3\n%d %d\n255\n",imgW, imgH);
		
	for(i = 0; i < imgW*imgH; i++){
		greyS = frame[i];

    	fprintf(file, "%u %u %u ", greyS, greyS, greyS);
		if((i % imgW) == 0 && i != 0){
			fprintf(file, "\n");
		}
	}
	
    fclose(file);
    print("Created picture file --> %s\n", fname);



	return 0;
}





