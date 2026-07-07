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
  BGT_DEVICE               = 2U,   /**< Select BGT for SPI read/write operation */
  LMX_DEVICE               = 1U,   /**< Select LMX for SPI read/write operation */
  PGA_DEVICE               = 0U    /**< Select PGA for SPI read/write operation */
} SPI_Device_Type_t;

int Init_SPI(XSpiPs *SpiInstancePtr, uint16_t SpiDeviceId);

static XSpiPs Spi0;


#endif
