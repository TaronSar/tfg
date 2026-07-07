
#ifndef DIGITAL_IO_CONFIG_H
#define DIGITAL_IO_CONFIG_H


#include "digital_io.h"


// OUTPUT
DIGITAL_IO_t DIGITAL_IO_PLL_CE =
{
  //.gpio_port = &Gpio0,
  .gpio_pin = 54,
  .set_mode = 0x1,
  .enable_pin = 0x1,
  .write_value  = 0x0,
};

DIGITAL_IO_t DIGITAL_IO_PLL_TRIG2 =
{
  //.gpio_port = &Gpio0,
  .gpio_pin = 55,
  .set_mode = 0x1,
  .enable_pin = 0x1,
  .write_value  = 0x0,
};

DIGITAL_IO_t DIGITAL_IO_PLL_TRIG1 =
{
  //.gpio_port = &Gpio0,
  .gpio_pin = 56,
  .set_mode = 0x0,
};

DIGITAL_IO_t DIGITAL_IO_PLL_MOD =
{
  //.gpio_port = &Gpio0,
  .gpio_pin  = 57,
  .set_mode  = 0x0,
};

DIGITAL_IO_t DIGITAL_IO_PLL_MUX_IN =
{
  //.gpio_port = &Gpio0,
  .gpio_pin  = 58,
  .set_mode  = 0x0,
};

DIGITAL_IO_t DIGITAL_IO_PGA_LDO_ENA =
{
  //.gpio_port = &Gpio0,
  .gpio_pin  = 54,
  .set_mode  = 0x1,
  .enable_pin = 0x1,
  .write_value  = 0x0,
};

DIGITAL_IO_t DIGITAL_IO_BGT_LDO_ENA =
{
  .gpio_pin  = 60,
  .set_mode  = 0x1,
  .enable_pin = 0x1,
  .write_value  = 0x0,
};


DIGITAL_IO_t DIGITAL_IO_BGT_POWER_ENA =
{
  .gpio_pin    =  62,
  .set_mode    = 0x1,
  .enable_pin  = 0x1,
  .write_value = 0x1,
};

int IOs_Init(XGpioPs* InstancePointer);



#endif

