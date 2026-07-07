#include "dma.h"
#include "xparameters.h"
#include "xil_printf.h"
#include "xil_types.h"


#define DMA_DEVICE_ADDRESS		XPAR_AXI_DMA_0_BASEADDR
#define DMA_TRANSFER_SIZE		64

//int hello_dma(){
int main(){
	dma_channel_conf dma_ch_adq;
	int Status;

	uint32_t data_dma_to_device[DMA_TRANSFER_SIZE];
	uint32_t data_device_to_dma[DMA_TRANSFER_SIZE];

	print("\n** NO DMA CONFIGURATION **\n");

	dma_ch_adq.dev_base_addr = DMA_DEVICE_ADDRESS;
	dma_ch_adq.stream_2_mm = 1;
	dma_ch_adq.mm_2_stream = 1;
	dma_ch_adq.irqs = DMA_DMASR_IOC_IRQ;
	dma_ch_adq.length = DMA_TRANSFER_SIZE;
	dma_ch_adq.AddrWidth = 32;



    xil_printf("Zynq SoC DMA application\n\r");

    // Initialize DMA-read data buffer with 32-bit incrementing counter data.
    for(u32 i=0; i < DMA_TRANSFER_SIZE; i++){
    	data_dma_to_device[i] = i;
    	data_device_to_dma[i] = 0;
    }

	dma_reset_core(dma_ch_adq);

	Xil_DCacheDisable();

	//DMA-read operation to move data to AXI-stream FIFO in PL
	dma_ch_adq.target_addr = data_dma_to_device;
	Status = dma_transfer_channel(dma_ch_adq, dma_rd);
	xil_printf("Status TRANSFER dma_rd: %d \n\r",Status);

	dma_ch_adq.target_addr = data_device_to_dma;
	Status = dma_transfer_channel(dma_ch_adq, dma_wr);
	xil_printf("Status TRANSFER dma_wr: %d \n\r",Status);

    for(u32 i=0; i < DMA_TRANSFER_SIZE; i++){
    	xil_printf("Data[%d]:%d\n\r",i,data_device_to_dma[i]);
    }
    return 0;
}
