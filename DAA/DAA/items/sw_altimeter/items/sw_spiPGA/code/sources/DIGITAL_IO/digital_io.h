#ifndef DIGITAL_IO_H
#define DIGITAL_IO_H


#include "xgpiops.h"

#include "xstatus.h"
#include <xil_printf.h>

#define GPIO_DEVICE_ID		XPAR_XGPIOPS_0_DEVICE_ID
#define	XGPIOPS_BASEADDR	XPAR_XGPIOPS_0_BASEADDR


typedef enum DIGITAL_IO_STATUS
{
  DIGITAL_IO_STATUS_OK = 0U,/**< 0=Status OK */
  DIGITAL_IO_STATUS_FAILURE = 1U/**< 1=Status Failed */
} DIGITAL_IO_STATUS_t;


typedef struct DIGITAL_IO
{
  XGpioPs * gpio_port;       /**< port number */
  const   u32 gpio_pin;      /**< pin number */
  const   u32 set_mode;
  const   u32 enable_pin;
  u32 		write_value;
} DIGITAL_IO_t;

int GPIOPS_0_init(XGpioPs* InstancePointer);

DIGITAL_IO_STATUS_t  DIGITAL_IO_Init( DIGITAL_IO_t *handler);

void DIGITAL_IO_SetOutputHigh(DIGITAL_IO_t *handler);

void DIGITAL_IO_SetOutputLow(DIGITAL_IO_t *handler);

int DIGITAL_IO_GetInput(DIGITAL_IO_t *handler);

static XGpioPs Gpio0;

#include "digital_io_extern.h"

#endif
