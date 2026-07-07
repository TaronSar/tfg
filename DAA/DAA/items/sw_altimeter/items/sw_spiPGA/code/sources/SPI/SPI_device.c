
#include "SPI_device.h"


int Init_SPI(XSpiPs *SpiInstancePtr, uint16_t SpiDeviceId){

	int Status;
	static XSpiPs_Config *SpiConfig;

	SpiConfig = XSpiPs_LookupConfig(SpiDeviceId);
			if (SpiConfig == NULL) {
				xil_printf("\nError 1\n");
				return XST_DEVICE_NOT_FOUND;
				}

		Status = XSpiPs_CfgInitialize(SpiInstancePtr,SpiConfig,SpiConfig->BaseAddress);
			if (Status != XST_SUCCESS) {
				xil_printf("\nError 2\n");
				return XST_FAILURE;
			}

		Status = XSpiPs_SelfTest(SpiInstancePtr);
			if (Status != XST_SUCCESS) {
				xil_printf("\nError 3\n");
				return XST_FAILURE;
			}

		u32 Options = XSPIPS_MANUAL_START_OPTION | XSPIPS_MASTER_OPTION | XSPIPS_FORCE_SSELECT_OPTION;
		int Status_o = XSpiPs_SetOptions(SpiInstancePtr, Options);
			if (Status_o != XST_SUCCESS) {
		        xil_printf("Error 4\n");
		        return XST_FAILURE;
		    	}

		Status =  XSpiPs_SetClkPrescaler(SpiInstancePtr, XSPIPS_CLK_PRESCALE_32);
			if (Status != XST_SUCCESS) {
				xil_printf("Error 5\n");
			    return XST_FAILURE;
			    }
return Status;
}
