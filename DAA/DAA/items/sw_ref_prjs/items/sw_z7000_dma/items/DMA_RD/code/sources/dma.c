#include "dma.h"
#include "xil_io.h"
#include "sleep.h"

static void set_reg(uint32_t addr, uint32_t val){

	 Xil_Out32(addr, (u32) val);
}

static int get_reg(uint32_t addr){

	return Xil_In32(addr);
}

static void wait_reg_bits(uint32_t addr, uint32_t bit_mask, uint32_t tries){

	uint32_t val;
	uint32_t try;
	uint32_t real_tries;

	if(tries == 0){ //Infinitive wait
		try = 0;
		real_tries = 1;	}
	do{
		//memmap_read(addr, &val);
		val = Xil_In32(addr);
		if(tries != 0)try++;
	}
	while(((val & bit_mask) == 0) && (try <= real_tries));

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

	if (conf.mm_2_stream == 1){
		conf.direction = dma_rd;
	    dmacr_reg_addr = get_reg_addr(conf, dma_dmacr);
	    xil_printf("Reset_mm2s:%d\n\r",dmacr_reg_addr);
	    set_reg(dmacr_reg_addr, DMA_DMACR_RESET);
	}

	if (conf.stream_2_mm == 1){
		conf.direction = dma_wr;
		dmacr_reg_addr = get_reg_addr(conf, dma_dmacr);
		xil_printf("Reset_s2mm:%d\n\r",dmacr_reg_addr);
		set_reg(dmacr_reg_addr, DMA_DMACR_RESET);
	}

	usleep(2);
    return 0;
}

uint8_t dma_config_channel(dma_channel_conf conf, dma_direction_t direction){

	uint32_t dmacr_reg_addr;
	uint32_t target_addr_reg_addr;
	uint32_t target_addr_msb_reg_addr;

	conf.direction = direction;

	if (direction == dma_rd){
		if (!conf.mm_2_stream) {
			xil_printf("MM2S channel is not supported\r\n");
			return XST_FAILURE;
			}
	}

	if (direction == dma_wr){
			if (!conf.stream_2_mm) {
				xil_printf("S2MM channel is not supported\r\n");
				return XST_FAILURE;
				}
		}

	dmacr_reg_addr           = get_reg_addr(conf, dma_dmacr);
	target_addr_reg_addr     = get_reg_addr(conf, dma_taddr);
	target_addr_msb_reg_addr = get_reg_addr(conf, dma_taddr_msb);

	/*Configure Irqs enabled*/
	set_reg(dmacr_reg_addr, conf.irqs);

	set_reg(target_addr_reg_addr,  ((uint32_t) (conf.target_addr)));
	set_reg(target_addr_msb_reg_addr, ((uint32_t) (conf.target_addr >> 32)));
    return 0;
}

uint8_t dma_transfer_channel(dma_channel_conf conf, dma_direction_t direction){

	int Status;
	uint32_t dmacr_reg_addr;
	uint32_t target_addr_reg_addr;
	uint32_t target_addr_msb_reg_addr;
	uint32_t dmalength_reg_addr;
	uint32_t sr_transfer_reg_addr;

	conf.direction = direction;

	if (direction == dma_rd){
		if (!conf.mm_2_stream) {
			xil_printf("MM2S channel is not supported\r\n");
			return XST_FAILURE;
			}
	}

	if (direction == dma_wr){
		if (!conf.stream_2_mm) {
			xil_printf("S2MM channel is not supported\r\n");
			return XST_FAILURE;
			}
	}

	dmacr_reg_addr           = get_reg_addr(conf, dma_dmacr);
	sr_transfer_reg_addr     = get_reg_addr(conf, dma_dmasr);
	target_addr_reg_addr     = get_reg_addr(conf, dma_taddr);
	target_addr_msb_reg_addr = get_reg_addr(conf, dma_taddr_msb);
	dmalength_reg_addr       = get_reg_addr(conf, dma_length);

	/*Configure Irqs enabled*/
	//set_reg(dmacr_reg_addr, conf.irqs);

	/*Configure Transfer*/
	set_reg(target_addr_reg_addr, ((uint32_t) (conf.target_addr)));

	if (conf.AddrWidth > 32){
	set_reg(target_addr_msb_reg_addr,((uint32_t) (conf.target_addr >> 32)));
	}

	set_reg(dmacr_reg_addr, dmacr_reg_addr | DMA_DMACR_RS);
	/* Start transfer */
	set_reg(dmalength_reg_addr, conf.length*4);
	usleep(1);
	/* Check Status Transfer  1: Transfer Complete. 0:Transfer in progress.*/
	if ((get_reg(sr_transfer_reg_addr) & DMA_DMASR_IDLE)){
		Status = 0;
		}
	else{
		// In progress
		Status = 1;
		}

	return Status;
}

uint8_t dma_get_irq(dma_channel_conf conf, dma_irq_t irqId){

	uint8_t fIrq = 0;
	uint32_t dmasr_reg_addr;
	uint32_t dmasr_reg;


	dmasr_reg_addr = get_reg_addr(conf, dma_dmasr);

	dmasr_reg = get_reg(dmasr_reg_addr);

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

	dmasr_reg = get_reg(dmasr_reg_addr);

    return dmasr_reg;
}

uint8_t dma_run_channel(dma_channel_conf conf ,dma_direction_t direction){

	uint32_t lenght_reg_addr;
	uint32_t dmacr_reg_addr;
	uint32_t dmacr_reg;

	conf.direction = direction;

	dmacr_reg_addr = get_reg_addr(conf, dma_dmacr);
	lenght_reg_addr = get_reg_addr(conf, dma_length);

	dmacr_reg = get_reg(dmacr_reg_addr);
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

	dmacr_reg = get_reg(dmacr_reg_addr);
	dmasr_reg = get_reg(dmasr_reg_addr);
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
