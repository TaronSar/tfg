

#include "digital_io.h"




int GPIOPS_0_init(XGpioPs* InstancePointer){

	int Status;
	XGpioPs_Config *ConfigPtr;
	ConfigPtr = XGpioPs_LookupConfig(GPIO_DEVICE_ID);

	if (ConfigPtr == NULL) {
		return XST_FAILURE;
	}

	/* Initialize the GPIO driver */
	Status = XGpioPs_CfgInitialize(InstancePointer,ConfigPtr ,ConfigPtr->BaseAddr );
	if (Status != XST_SUCCESS) {
		xil_printf("Gpio Initialization Failed\r\n");
	    return XST_FAILURE;
	}

	XGpioPs_SetDirection(InstancePointer, 2, 0x0000);
	return Status;
}

DIGITAL_IO_STATUS_t DIGITAL_IO_Init( DIGITAL_IO_t * handler){


		XGpioPs_SetDirectionPin(handler->gpio_port, handler->gpio_pin, handler->set_mode);

		if (handler->set_mode == 1){
		XGpioPs_SetOutputEnablePin(handler->gpio_port, handler->gpio_pin, handler->enable_pin);
		XGpioPs_WritePin(handler->gpio_port, handler->gpio_pin, handler->write_value);
		}
		return DIGITAL_IO_STATUS_OK;
}

void DIGITAL_IO_SetOutputHigh( DIGITAL_IO_t * handler){

	XGpioPs_WritePin(handler->gpio_port, handler->gpio_pin, 0x1);
}

void DIGITAL_IO_SetOutputLow( DIGITAL_IO_t * handler){

	XGpioPs_WritePin(handler->gpio_port, handler->gpio_pin, 0x0);
}

int  DIGITAL_IO_GetInput( DIGITAL_IO_t *handler){

	int Data_Read;

	XGpioPs_SetDirectionPin(handler->gpio_port, handler->gpio_pin, handler->set_mode);
	Data_Read = XGpioPs_ReadPin(handler->gpio_port, handler->gpio_pin);

	return Data_Read;
}

