
#include "main.h"
#include "sleep.h"
#ifdef SDT
#include "xinterrupt_wrap.h"

#endif



#define GPIO_DEVICE_ID		XPAR_XGPIOPS_0_DEVICE_ID
#define SPI_DEVICE_ID_0		XPAR_XSPIPS_0_DEVICE_ID

#define GPIO_INTERRUPT_ID	XPMC_GPIO_INT_ID


int main(){

	init_platform();
	int Status;

	Status = GPIOPS_0_init(&Gpio0);

	Status = IOs_Init(&Gpio0);

	Status = Init_SPI(&Spi0, SPI_DEVICE_ID_0);

	DIGITAL_IO_SetOutputHigh(&DIGITAL_IO_PLL_TRIG2);

	pga_ldo_enable(&Spi0);

    Status = pga112_init(&Spi0, PGA_GAIN);

    Status = pga112_set_gain(&Spi0, 0U);
    Status = pga112_set_gain(&Spi0, 1U);
    Status = pga112_set_gain(&Spi0, 2U);
    Status = pga112_set_gain(&Spi0, 3U);
    Status = pga112_set_gain(&Spi0, 4U);
    Status = pga112_set_gain(&Spi0, 6U);
    Status = pga112_set_gain(&Spi0, 7U);

	Status = pga_read_data(&Spi0);

	if (Status != XST_SUCCESS) {
		xil_printf("SPI Initialization Failed\r\n");
		return XST_FAILURE;
	}
	xil_printf("Sucessfull: %d\r\n",Status);

	cleanup_platform();
	return 0;
}
