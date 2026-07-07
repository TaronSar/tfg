
#include "digital_io_conf.h"


int IOs_Init(XGpioPs* InstancePointer){

	int Status;

	DIGITAL_IO_PLL_CE.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_CE);  			// 54

	DIGITAL_IO_PLL_TRIG2.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_TRIG2);		// 55

	DIGITAL_IO_PLL_TRIG1.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_TRIG1);		// 56

	DIGITAL_IO_PLL_MOD.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_MOD);			// 57

	DIGITAL_IO_PLL_MUX_IN.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_MUX_IN);		// 58

	DIGITAL_IO_PGA_LDO_ENA.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PGA_LDO_ENA);		// 59

	DIGITAL_IO_BGT_LDO_ENA.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_BGT_LDO_ENA);		// 60

	/*DIGITAL_IO_PLL_LDO_ENA.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_PLL_LDO_ENA);		// 61
    */

	DIGITAL_IO_BGT_POWER_ENA.gpio_port = InstancePointer;
	Status = DIGITAL_IO_Init(&DIGITAL_IO_BGT_POWER_ENA);	// 62


	Status = XST_SUCCESS;

	return Status;
}





