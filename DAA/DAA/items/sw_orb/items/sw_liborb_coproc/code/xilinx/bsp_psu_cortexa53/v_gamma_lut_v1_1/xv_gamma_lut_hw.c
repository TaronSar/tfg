//----------------------------------------------------------------------//
//                         GAMMA register linux driver                   //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#include "xv_gamma_lut_hw.h"


uint32_t XV_gamma_lut_In32(uint32_t address){
	uint32_t reg;
	mem_map mm;
	memmap_init(&mm, address);
	memmap_read(mm, address, &reg);

	memmap_close(mm);

	return reg;
}

void XV_gamma_lut_Out32(uint32_t address, uint32_t data){
	mem_map mm;
	memmap_init(&mm, address);
	memmap_write(mm, address, data);

	memmap_close(mm);

}


