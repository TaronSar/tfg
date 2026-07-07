#ifndef PGA112_H_
#define PGA112_H_


#include "xspips.h"
#include "../../PS_DRIVERs/SPI/SPI_device.h"
#include "../../PS_DRIVERs/DIGITAL_IO/digital_io.h"


/*
==============================================================================
   1. DEFINITIONS
==============================================================================
 */

/**
 * @brief The maximum number of supported gain by PGA112 device.
 */
#define PGA112_MAX_NUMBER_SUPPORTED_GAIN       	(7U)        /**< binary gain 128 */

/**
 * @brief PGA112 default configuration value.
 */
#define PGA112_BASE_CONF			(PGA112_CMD_WRITE | PGA112_BINARY_GAIN_32 | PGA112_CH1)

/***************************** Define Libraries *******************************/
#define PGA_GAIN    (4U)
#define SPI_INTR_ID     XPAR_XSPIPS_0_INTR

/*
==============================================================================
   2. TYPES
==============================================================================
 */

/**
 * \brief SPI commands, used to control PGA112 device.
 * @{
 */
typedef enum
{
  PGA_STATUS_SUCCESS  = 0L,        /**< Success */
  PGA_STATUS_FAIL     = 1L,        /**< Fail */
  PGA_STATUS_NA       = 2L         /**< Feature not available */
} Pga_Status_t;

// Mode
typedef enum
{
  PGA112_CMD_READ           = 0x6A00U,     /**< Read command */
  PGA112_CMD_WRITE          = 0x2A00U,     /**< Write command */
  PGA112_CMD_NOP_WRITE      = 0x0000U,     /**< No OPeration command */
  PGA112_CMD_SDN_DIS_WRITE  = 0xE100U,     /**< Exit Shutdown mode */
  PGA112_CMD_SDN_EN_WRITE   = 0xE1F1U      /**< Enter Shutdown mode */
} Pga112_Command_t;

//Select Channel
typedef enum
{
  PGA112_CH0_VCAL          = 0x0000U,     /**< Input MUX channel 0 and VCAL input */
  PGA112_CH1               = 0x0001U      /**< Input MUX channel 1 */
} Pga112_Channel_t;

//Several Gain
typedef enum
{
  PGA112_BINARY_GAIN_1     = 0x0000U,     /**< binary gain 1 */
  PGA112_BINARY_GAIN_2     = 0x0010U,     /**< binary gain 2 */
  PGA112_BINARY_GAIN_4     = 0x0020U,     /**< binary gain 4 */
  PGA112_BINARY_GAIN_8     = 0x0030U,     /**< binary gain 8 */
  PGA112_BINARY_GAIN_16    = 0x0040U,     /**< binary gain 16 */
  PGA112_BINARY_GAIN_32    = 0x0050U,     /**< binary gain 32 */
  PGA112_BINARY_GAIN_64    = 0x0060U,     /**< binary gain 64 */
  PGA112_BINARY_GAIN_128   = 0x0070U      /**< binary gain 128 */
} Pga112_Binary_Gain_t;

/**
 * \brief PGA112 SPI function pointer, responsible for SPI data transmission via SPI protocol.
 * @{
 */
typedef s32 (*sendSPIFunction)(XSpiPs *SpiInstancePtr, u8 *SendBufPtr,u8 *RecvBufPtr, u32 ByteCount);

/**
 * \brief An instance of PGA this structure
 * @{
 */
typedef struct
{
	Pga112_Command_t 		Command;
	Pga112_Channel_t 		Channel;
	Pga112_Binary_Gain_t	Gain;
	XSpiPs*					SPI_devicePtr;
	sendSPIFunction         sendSPI;
} PGA112_Object;

// Device

#define MAX_PGA_GAIN_LEVEL     PGA112_MAX_NUMBER_SUPPORTED_GAIN
#define PGA112_BASE_CONF		(PGA112_CMD_WRITE | PGA112_BINARY_GAIN_32 | PGA112_CH1)
#define XSPIPS_PGA_SPI_MAX_SIZE  16
#define XSPIPS_TPM_TX_HEAD_SIZE	 2

void pga_ldo_enable();

//int pga112_init( uint16_t gain_level);
int pga112_init( PGA112_Object* pga_handle, uint16_t gain_level, XSpiPs *SpiInstancePtr );

int pga112_set_gain( XSpiPs *SpiInstancePtr, uint16_t gain_level);

int pga_read_data();

#endif
