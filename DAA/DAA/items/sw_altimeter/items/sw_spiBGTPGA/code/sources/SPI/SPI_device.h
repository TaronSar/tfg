#ifndef SPI_device_h
#define SPI_device_h

#include "xparameters.h"	/* EDK generated parameters */
#include "xspips.h"
#include "xil_printf.h"

/**
 * \brief Select SPI device for read/write operation.
 * @{
 */
typedef enum
{
  LMX_DEVICE               = 2U,   /**< Select LMX for SPI read/write operation */
  BGT_DEVICE               = 1U,   /**< Select BGT for SPI read/write operation */
  PGA_DEVICE               = 0U    /**< Select PGA for SPI read/write operation */
} SPI_Device_Type_t;


int Init_SPI(XSpiPs *SpiInstancePtr, uint16_t SpiDeviceId, uint8_t slave_device);



#endif
