#ifndef PGA_H_
#define PGA_H_

#include "xparameters.h"
#include <stdio.h>
#include <stdbool.h>
#include "PGA112.h"


static volatile  uint16_t pga112_global_gain = 0; /**< Current PGA112 gain */

static volatile  uint16_t pga112_global_config = PGA112_BASE_CONF; /**< Current PGA112 configuration */

/**************************** Type Definitions *******************************/

static Pga112_Binary_Gain_t pga112_get_binary_gain(uint16_t gain_idx);

int pga112_get_gain(uint16_t* gain_level);

int pga_transfer_data(XSpiPs *SpiInstancePtr, uint16_t Command, uint32_t Length);

/*****************************************************************************/
void pga_ldo_enable(){

	//DIGITAL_IO_SetOutputHigh(&DIGITAL_IO_PGA_LDO_ENA);
	DIGITAL_IO_SetOutputHigh(&DIGITAL_IO_PLL_CE);
}

int pga112_init( PGA112_Object* pga_handle, uint16_t gain_level, XSpiPs *SpiInstancePtr ){

	pga_handle->Gain			 = gain_level;
	pga_handle->SPI_devicePtr = SpiInstancePtr;
	return (pga112_set_gain( pga_handle->SPI_devicePtr, pga_handle->Gain));
}


int pga112_set_gain(XSpiPs *SpiInstancePtr, uint16_t gain_level){

	int Status;
	Pga112_Binary_Gain_t gain_val;

	if(gain_level > PGA112_MAX_NUMBER_SUPPORTED_GAIN)
	  	  {	return (XST_FAILURE);
	  	  }
	/* Get PGA112 gain value from the selected index */
	pga112_global_gain = gain_level;
	gain_val = pga112_get_binary_gain(gain_level);
	pga112_global_config = (PGA112_CMD_WRITE | gain_val | PGA112_CH1);
	xil_printf("Valor de ganancia: %d\n\r",pga112_global_config);

	Status = pga_transfer_data(SpiInstancePtr, (u16) pga112_global_config, (u32) 2);
	if (Status != XST_SUCCESS) {
			xil_printf("Error 7\n");
			return XST_FAILURE;
			}
	xil_printf("Status: %d\n\r",Status);
	return (Status);
}

int pga_transfer_data(XSpiPs *SpiInstancePtr, uint16_t Command, uint32_t Length){

	int Status;
	u8 TXBuffer[128];
	u8 RXBuffer[128];

	TXBuffer[0] = (u8) ((Command & 0xFF00) >> 8);
	TXBuffer[1] = (u8) ((Command & 0x00FF));

	Status = XSpiPs_PolledTransfer(SpiInstancePtr, TXBuffer, RXBuffer, Length);

	return Status;
}

int pga_read_data(XSpiPs *SpiInstancePtr){

	int Status;
	uint16_t Command = PGA112_CMD_READ;
	u8 TXBuffer[16];
	uint32_t Length =2;

	TXBuffer[0] = (u8) ((Command & 0xFF00) >> 8);
	TXBuffer[1] = (u8) ((Command & 0x00FF));

	Status = XSpiPs_PolledTransfer(SpiInstancePtr, TXBuffer, NULL, Length);

	Command = 0x0000U;
	TXBuffer[0] = (u8) ((Command & 0xFF00) >> 8);
	TXBuffer[1] = (u8) ((Command & 0x00FF));
	Status = XSpiPs_PolledTransfer(SpiInstancePtr, TXBuffer, NULL, Length);

	return Status;
}

static Pga112_Binary_Gain_t pga112_get_binary_gain(uint16_t gain_idx)
{
	Pga112_Binary_Gain_t gain_val;

  switch (gain_idx)
  {
  case 0U:
    gain_val = PGA112_BINARY_GAIN_1;
    break;

  case 1U:
    gain_val = PGA112_BINARY_GAIN_2;
    break;

  case 2U:
    gain_val = PGA112_BINARY_GAIN_4;
    break;

  case 3U:
    gain_val = PGA112_BINARY_GAIN_8;
    break;

  case 5U:
    gain_val = PGA112_BINARY_GAIN_32;
    break;

  case 6U:
    gain_val = PGA112_BINARY_GAIN_64;
    break;

  case 7U:
    gain_val = PGA112_BINARY_GAIN_128;
    break;

  default:
  case 4U:
    gain_val = PGA112_BINARY_GAIN_16;
    break;
  }
  return (gain_val);
}

#endif
