/**
 * @file pixel_pack.c
 * @brief Library for pixel pack IP from PYNQ.
 * 
 * @date 	February, 2024
 * @author	Victor Morales, Sergio Cuenca
 * @company Embention
 */



#include "pixel_pack.h"

static void set_reg(uint32_t addr, uint32_t val){

    mem_map mm;
	memmap_init(&mm, addr);
	
	memmap_write(mm, addr, val);

	memmap_close(mm);

}
static void get_reg(uint32_t addr, uint32_t *val){

    mem_map mm;
	memmap_init(&mm, addr);

	memmap_read(mm, addr, val);

	memmap_close(mm);

}


uint8_t pixel_pack_setup(pixel_pack_conf config)
{	
	uint32_t check, ret;
	
	set_reg(config.dev_base_addr + 0x10U , (uint32_t)(config.mode));
	get_reg(config.dev_base_addr + 0x10U , &check);

	if(check == (uint32_t)(config.mode)) ret = 0;
	else ret = 1;
	print("pixel pack conf: %d\n",ret);
	return ret;
}

