//----------------------------------------------------------------------//
//                         DMA Linux Driver                             //
// Author: Victor Morales                                               //
// Company: Embention                                                   //
// Date: November 2023                                                  //
//----------------------------------------------------------------------//

#include "dma.h"

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

static void wait_reg_bits(uint32_t addr, uint32_t bit_mask, uint32_t tries){

	uint32_t val;
	uint32_t try;
	uint32_t real_tries;

    mem_map mm;
	memmap_init(&mm, addr);

	if(tries == 0){ //Infinitive wait
		try = 0;
		real_tries = 1;
	}
	
	do{
		memmap_read(mm, addr, &val);
		if(tries != 0)try++;
		usleep(100);
	}
	while(((val & bit_mask) == 0) && (try <= real_tries));

	memmap_close(mm);
}

static uint32_t get_reg_addr(dma_channel_conf conf, dma_register_t reg){
	
	uint32_t reg_addr;

	switch(reg){
		case dma_dmacr: 
			reg_addr = conf.dev_base_addr + DMA_MM2S_DMACR_OFFS;
			break;
    	case dma_dmasr: 
			reg_addr = conf.dev_base_addr + DMA_MM2S_DMASR_OFFS;
			break;
    	case dma_taddr:
			reg_addr = conf.dev_base_addr + DMA_MM2S_SA_OFFS;
			break;
    	case dma_taddr_msb: 
			reg_addr = conf.dev_base_addr + DMA_MM2S_SA_MSB_OFFS;
			break;
    	case dma_length:
			reg_addr = conf.dev_base_addr + DMA_MM2S_LENGTH_OFFS;
			break;
		default:
			reg_addr = 0U;
			break;
	}

	if(conf.direction == dma_wr) reg_addr = reg_addr + DMA_CHANNEL_OFFS;

	return reg_addr;
}

uint8_t dma_reset_core(dma_channel_conf conf){

	uint32_t dmacr_reg_addr;
	uint32_t dmacr_reg;

	dmacr_reg_addr = get_reg_addr(conf, dma_dmacr);

	get_reg(dmacr_reg_addr, &dmacr_reg);
	set_reg(dmacr_reg_addr, dmacr_reg | DMA_DMACR_RESET);
	usleep(50000);
    return 0;
}

uint8_t dma_config_channel(dma_channel_conf conf){
	
	uint32_t dmacr_reg_addr;
	uint32_t target_addr_reg_addr;
	uint32_t target_addr_msb_reg_addr;

	dmacr_reg_addr = get_reg_addr(conf, dma_dmacr);
	target_addr_reg_addr = get_reg_addr(conf, dma_taddr);
	target_addr_msb_reg_addr = get_reg_addr(conf, dma_taddr_msb);
	
	//Configure Irqs enabled
	set_reg(dmacr_reg_addr, conf.irqs);
	set_reg(target_addr_reg_addr, (uint32_t)(conf.target_addr & 0xFFFFFFFFU));
	set_reg(target_addr_msb_reg_addr, (uint32_t)((conf.target_addr >> 32U)& 0xFFFFFFFFU));
    return 0;
}

uint8_t dma_get_irq(dma_channel_conf conf, dma_irq_t irqId){

	uint8_t fIrq = 0;
	uint32_t dmasr_reg_addr;
	uint32_t dmasr_reg;
	

	dmasr_reg_addr = get_reg_addr(conf, dma_dmasr);

	get_reg(dmasr_reg_addr, &dmasr_reg);

	fIrq = (uint8_t)((dmasr_reg >> irqId) & 0x1U);
	if(fIrq == 1){
		//print("Interruption raised: %d\n", irqId);
		dmasr_reg = dmasr_reg | (((uint32_t)1U) << irqId);
		set_reg(dmasr_reg_addr, dmasr_reg);
	}
    return fIrq;
}



uint32_t dma_get_length(dma_channel_conf conf){

	uint32_t dmasr_reg_addr;
	uint32_t dmasr_reg;
	

	dmasr_reg_addr = get_reg_addr(conf, dma_length);

	get_reg(dmasr_reg_addr, &dmasr_reg);

    return dmasr_reg;
}

uint8_t dma_run_channel(dma_channel_conf conf){

	uint32_t lenght_reg_addr;
	uint32_t dmacr_reg_addr;
	uint32_t dmacr_reg;

	dmacr_reg_addr = get_reg_addr(conf, dma_dmacr);
	lenght_reg_addr = get_reg_addr(conf, dma_length);

	get_reg(dmacr_reg_addr, &dmacr_reg);
	set_reg(dmacr_reg_addr, dmacr_reg | DMA_DMACR_RS);
	set_reg(lenght_reg_addr, conf.length);

    return 0;
}

uint8_t dma_stop_channel(dma_channel_conf conf){

	uint32_t dmacr_reg_addr;
	uint32_t dmasr_reg_addr;
	uint32_t dmacr_reg;
	uint32_t dmasr_reg;

	dmacr_reg_addr = get_reg_addr(conf, dma_dmacr);
	dmasr_reg_addr = get_reg_addr(conf, dma_dmasr);

	get_reg(dmacr_reg_addr, &dmacr_reg);
	get_reg(dmasr_reg_addr, &dmasr_reg);
	set_reg(dmacr_reg_addr, dmacr_reg & ~((uint32_t)DMA_DMACR_RS));

	wait_reg_bits(dmasr_reg_addr,DMA_DMASR_HALT,DMA_WAIT_TRIES);

    return 0;
}



uint8_t dma_wait_idle(dma_channel_conf conf){

	uint32_t dmasr_reg_addr;

	dmasr_reg_addr = get_reg_addr(conf, dma_dmasr);
	
	wait_reg_bits(dmasr_reg_addr,DMA_DMASR_IDLE, DMA_WAIT_TRIES);

    return 0;
}