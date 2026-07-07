/* Enable C linkage if header is included in C++ files */
#ifdef __cplusplus
extern "C"
{
#endif /* __cplusplus */
/*
==============================================================================
   1. INCLUDE FILES
==============================================================================
 */
#include "xparameters.h"
#include "platform.h"
#include "xplatform_info.h"
#include <xil_printf.h>


/* Include PS Drivers Components */
#include "../PS_DRIVERs/DIGITAL_IO/digital_io.h"
#include "../PS_DRIVERs/SPI/SPI_device.h"



/* Include Embedded Components */
#include "../RF_DEV/PGA/PGA112.h"
#include "../RF_DEV/BGT24/bgt.h"
#include "../RF_DEV/BGT24/bgt24mtr1x.h"
#include "../RF_DEV/PLL/PLL.h"
#include "../RF_DEV/PLL/LMX249x.h"

/*
==============================================================================
   2. DEFINITIONS
==============================================================================
 */


#define DISABLED	        (0U)
#define ENABLED		     (1U)

#define DOPPLER_MODULATION	(0U)
#define FMCW_MODULATION		(1U)

//=========================== BGT / PGA CONFIG =================================//


#define DUTY_CYCLE_ENABLE			(1U)		/**< Enable [1] or Disable [0] duty cycle of Position2Go via BGT & PLL On/Off */

#define BGT_TX_POWER				   (7U)		/**< BGT TX Power levels: [1 - 7], Minimum = 1 & Maximum = 7 */

#define LNA_GAIN_ENABLE				(1U)		/**< Enable [1] or Disable [0] LNA Gain in BGT TX */

#define PGA_GAIN					   (4U)		/**< PGA112 default gain value, [0 - 7] */







//================================== RF CONFIG =================================//
/**
 * @brief The Radar duty cycle state enabled/disabled.
 */


#define BSP_NUM_TX_ANTENNAS        BGT24MTR1X_NUM_TX_ANTENNAS      /**< TX antennas in BGT24MTR12 */

#define BSP_NUM_RX_ANTENNAS        BGT24MTR1X_NUM_RX_ANTENNAS      /**< RX antennas in BGT24MTR12 */

#define BSP_NUM_TEMP_SENSORS       BGT24MTR1X_NUM_TEMP_SENSORS     /**< Number of temperature sensors in BGT24MTR12 */

#define BSP_MAX_TX_POWER_LEVEL     BGT24MTR1X_MAX_TX_POWER_LEVEL   /**< Maximum BGT TX output power SPI input value range is [1 - 7] supported by BGT24MTR1x. */

#define BSP_MIN_RF_FREQUENCY_KHZ   BGT24MTR1X_MIN_RF_FREQUENCY_KHZ /**< Minimum RF frequency supported by BGT24MTR1x in kHz */

#define BSP_MAX_RF_FREQUENCY_KHZ   BGT24MTR1X_MAX_RF_FREQUENCY_KHZ /**< Maximum RF frequency supported by BGT24MTR1x in kHz */

static uint8_t bsp_duty_cycle_enable = DUTY_CYCLE_ENABLE;
/*
==============================================================================
   3. FUNCTION PROTOTYPES
==============================================================================
 */

static void get_raw_data(void);

int PS_RF_init();
/* Disable C linkage for C++ files */
#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */