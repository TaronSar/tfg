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

#include "DIGITAL_IO/digital_io.h"
#include "SPI/SPI_device.h"

//#include "DIGITAL_IO/digital_io_conf.h"

// Include Embedded Components
#include "PGA/PGA112.h"
#include "BGT24/bgt.h"
#include "BGT24/bgt24mtr1x.h"


/*
==============================================================================
   2. DEFINITIONS
==============================================================================
 */


#define DISABLED	        (0U)
#define ENABLED		     (1U)

#define DOPPLER_MODULATION	(0U)
#define FMCW_MODULATION		(1U)

//=========================== BGT / PGA CONFIG =============================//


#define DUTY_CYCLE_ENABLE			(1U)		/**< Enable [1] or Disable [0] duty cycle of Position2Go via BGT & PLL On/Off */

#define BGT_TX_POWER				   (7U)		/**< BGT TX Power levels: [1 - 7], Minimum = 1 & Maximum = 7 */

#define LNA_GAIN_ENABLE				(1U)		/**< Enable [1] or Disable [0] LNA Gain in BGT TX */

#define PGA_GAIN					   (4U)		/**< PGA112 default gain value, [0 - 7] */



/**
 * @brief The Radar duty cycle state enabled/disabled.
 */
static uint8_t bsp_duty_cycle_enable = DUTY_CYCLE_ENABLE;

/*
==============================================================================
   3. FUNCTION PROTOTYPES
==============================================================================
 */

static void get_raw_data(void);


/* Disable C linkage for C++ files */
#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */