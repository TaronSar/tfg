//----------------------------------------------------------------------//
//                         VDMA Linux Driver                          //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#include "vdma.h"

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

static uint32_t get_reg_addr(vdma_channel_conf conf, vdma_register_t reg){
	
	uint32_t reg_addr;

	switch(reg){
		case vdma_vdmacr: 
			reg_addr = conf.dev_base_addr + VDMA_MM2S_VDMACR_OFFS;
			break;
    	case vdma_vdmasr: 
			reg_addr = conf.dev_base_addr + VDMA_MM2S_VDMASR_OFFS;
			break;
    	case vdma_str_addr: 
			reg_addr = conf.dev_base_addr + VDMA_MM2S_START_ADDR;
			break;
    	case vdma_h_size: 
			reg_addr = conf.dev_base_addr + VDMA_MM2S_HSIZE_OFFS;
			break;
    	case vdma_v_size: 
			reg_addr = conf.dev_base_addr + VDMA_MM2S_VSIZE_OFFS;
			break;
    	case vdma_frm_dly_str: 
			reg_addr = conf.dev_base_addr + VDMA_MM2S_FRMDLY_STRIDE_OFFS;
			break;
		default:
			reg_addr = 0U;
			break;
	}

	if(conf.direction == vdma_wr && reg_addr != 0U){
		if(reg == vdma_vdmacr || reg == vdma_vdmasr) reg_addr = reg_addr + VDMA_CHANNEL_OFFS;
		else  reg_addr = reg_addr + VDMA_CHANNEL_OFFS_B;
	}

	return reg_addr;
}

static uint8_t set_start_addr(vdma_channel_conf conf, uint32_t start_addrs[], uint8_t n_str_addr){
    uint8_t i, res;
	uint32_t str_addr_reg_addr;
	uint32_t nstr_addr_reg_addr;

    if(n_str_addr <= VDMA_MAX_FRAME_BUFF){

		str_addr_reg_addr = get_reg_addr(conf, vdma_str_addr);

    	for(i = 0; i < n_str_addr; i++){
			nstr_addr_reg_addr = str_addr_reg_addr + (i*VDMA_SRT_ADDR_OFFS);
			conf.start_addrs[i] = start_addrs[i];
	    	set_reg(nstr_addr_reg_addr, (uint32_t)start_addrs[i]);
    	}
		res = 0;
	}		
	else res = 1;

	return res;
}


uint8_t vdma_reset_channel(vdma_channel_conf conf){

	uint32_t vdmacr_reg_addr;
	uint32_t vdmacr_reg;

	vdmacr_reg_addr = get_reg_addr(conf, vdma_vdmacr);
	get_reg(vdmacr_reg_addr, &vdmacr_reg);
	set_reg(vdmacr_reg_addr, vdmacr_reg | VDMA_VDMACR_RESET);	
	
    return 0;
}

uint8_t vdma_config_channel(vdma_channel_conf conf){
	
	uint32_t vdmacr_reg_addr;
	uint32_t vsize_reg_addr;
	uint32_t hsize_reg_addr;
	uint32_t frmdly_stride_reg_addr;
	uint32_t vdmacr_reg;

	vdmacr_reg_addr = get_reg_addr(conf, vdma_vdmacr);
	vsize_reg_addr = get_reg_addr(conf, vdma_v_size);
	hsize_reg_addr = get_reg_addr(conf, vdma_h_size);
	frmdly_stride_reg_addr = get_reg_addr(conf, vdma_frm_dly_str);
	set_reg(vdmacr_reg_addr, conf.vdmacr);

	get_reg(vdmacr_reg_addr, &vdmacr_reg);
	vdmacr_reg = (vdmacr_reg & ~(0xFF<<VDMA_VDMACR_FRMCNT_OFFS)) | (conf.n_frame_buff<<VDMA_VDMACR_FRMCNT_OFFS);
	
	set_reg(vdmacr_reg_addr, vdmacr_reg);

    if(set_start_addr(conf, conf.start_addrs, conf.n_frame_buff) != 0) return 1;

	set_reg(hsize_reg_addr,(uint32_t)(conf.h_size)*VDMA_PX_WIDTH);
	set_reg(vsize_reg_addr,(uint32_t)0U);
	set_reg(frmdly_stride_reg_addr,(uint32_t)((conf.h_size)*VDMA_PX_WIDTH)&0xFFFFU);

    return 0;
}


uint8_t vdma_get_irq(vdma_channel_conf conf, vdma_irq_t irqId){
	uint8_t fIrq = 0;
	uint32_t vdmasr_reg_addr;
	uint32_t vdmasr_reg;

	vdmasr_reg_addr = get_reg_addr(conf, vdma_vdmasr);


	get_reg(vdmasr_reg_addr, &vdmasr_reg);
	fIrq = (uint8_t)((vdmasr_reg >> irqId) & 0x1U);
	if(fIrq == 1){
		//print("Interruption raised: %d\n", irqId);
		vdmasr_reg = vdmasr_reg | (((uint32_t)1U) << irqId); //Clean
		set_reg(vdmasr_reg_addr, vdmasr_reg);
	}
    return fIrq;
}

uint8_t vdma_update_frame_addr(vdma_channel_conf conf, uint32_t fAddr){
	uint32_t strAddrs[1] = {fAddr};
	return set_start_addr(conf, strAddrs, 1U);
}


uint8_t vdma_run_channel(vdma_channel_conf conf){
	uint32_t vdmacr_reg;
	uint32_t vdmacr_reg_addr;
	uint32_t v_size_reg_addr;

	vdmacr_reg_addr = get_reg_addr(conf, vdma_vdmacr);
	v_size_reg_addr = get_reg_addr(conf, vdma_v_size);

	get_reg(vdmacr_reg_addr, &vdmacr_reg);
	vdmacr_reg = vdmacr_reg | VDMA_VDMACR_RS; // Run
	set_reg(vdmacr_reg_addr, vdmacr_reg);
	set_reg(v_size_reg_addr,(uint32_t)conf.v_size); //LAST STEP, this trigger the transmission

    return 0;
}



