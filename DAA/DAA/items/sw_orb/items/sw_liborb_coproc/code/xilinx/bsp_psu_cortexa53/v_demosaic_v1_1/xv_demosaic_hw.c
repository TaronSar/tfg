//----------------------------------------------------------------------//
//                     Demosaic register linux driver                   //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#include "xv_demosaic_hw.h"



uint32_t XV_demosaic_In32(uint32_t address){
	uint32_t reg;

    mem_map mm;
	memmap_init(&mm, address);
	memmap_read(mm, address, &reg);

	memmap_close(mm);

	return reg;
}

void XV_demosaic_Out32(uint32_t address, uint32_t data){

    mem_map mm;
	memmap_init(&mm, address);
	memmap_write(mm, address, data);

	memmap_close(mm);

}
