#include "digital_io_conf.h"


int IOs_Init(XGpioPs* InstancePointer){

	int Status;

	DIGITAL_IO_PLL_CE.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_CE);

	DIGITAL_IO_PLL_TRIG2.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_TRIG2);

	DIGITAL_IO_PLL_TRIG1.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_TRIG1);

	DIGITAL_IO_PLL_MOD.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_MOD);

	DIGITAL_IO_PLL_MUX_IN.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_MUX_IN);

	DIGITAL_IO_PGA_LDO_ENA.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PGA_LDO_ENA);

	DIGITAL_IO_BGT_LDO_ENABLE.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_BGT_LDO_ENABLE);

	Status = XST_SUCCESS;

	return Status;
}