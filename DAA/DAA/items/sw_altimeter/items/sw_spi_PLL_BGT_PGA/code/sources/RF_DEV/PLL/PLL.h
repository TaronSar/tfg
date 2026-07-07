#ifndef PLL_H_
#define PLL_H_

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

#include "LMX249x.h"


/*
==============================================================================
   2. DEFINITIONS
==============================================================================
*/

#define PLL_RAMP_DOWM_TIME_USEC		(100U)  /*!< Ramp down time for SawTooth Chirps in the PLL */

#define PLL_STEADY_STATE_USEC   	(100U)  /*!< Steady state delay before starting next chirp in the PLL */

#define PLL_RAMP_GUARD_FREQ_MHZ		(0.5f)   /*!< PLL lower and upper frequency guard band needed for identical multiple ramps */

#define MAX_BANDWIDTH_MHZ 			(200U)   /*!< Bandwidth (units in MHz), [0 - 200MHz] */

#define DEFAULT_CHIRP_TIME_USEC 	(300U)   /*!< Default chirp time in usec */

/*
==============================================================================
   3. FUNCTION PROTOTYPES
==============================================================================
 */

/**
 * \brief  This function sends the general configurations to PLL via SPI.
 *         It is used after every power up of PLL in duty cycle mode.
 *
 * \param[in] *pll_handle  Pointer to the handle for PLL, all PLL settings are controlled through this handle
 *
 */
int pll_init(Lmx249x_Object_t* pll_handle, XSpiPs *SpiInstancePtr);

/**
 * \brief  This function configures the ramps generation pattern i.e. up chirp, down chirp and their order of generation.
 *         It used bandwidth and chirp time parameters in to considerations to configure ramps.
 *
 * \param[in] *pll_handle  Pointer to the handle for PLL, all PLL settings are controlled through this handle
 *
 */
void pll_configure_ramps(void* pll_handle);

/**
 * \brief  This function enables the ramps generation through SPI command to the PLL.
 *         Ramps are started by enabling the DIGITAL_IO_PLL_TRIG1 pin.
 *
 * \param[in] *pll_handle  Pointer to the handle for PLL, all PLL settings are controlled through this handle
 *
 */
int pll_enable_ramps(void* pll_handle);

/**
 * \brief  This function disables the ramps generation through SPI command to the PLL.
 *
 * \param[in] *pll_handle  Pointer to the handle for PLL, all PLL settings are controlled through this handle
 *
 */
int pll_disable_ramps(void* pll_handle);

/**
 * \brief  This function is used to trigger the start generation of ramps.
 */
void pll_trigger_ramp(void);

/**
 * \brief  This function is used to bring the PLL trigger to down state.
 */
void pll_release_ramp_trigger(void);

/**
 * \brief  This function is used to power-up the PLL.
 */
void pll_power_up(void);

/**
 * \brief  This function is used to power-down the PLL.
 */
void pll_power_down(void);

/**
 * \brief  This function defines the protocol for updating the PLL configurations in case bandwidth or chirp-time or modulation changes.
 *
 * \param[in] *pll_handle      Pointer to the handle for PLL, all PLL settings are controlled through this handle
 * \param[in] modulation_type  Modulation type, 0 for Doppler modulation and 1 for FMCW modulation
 *
 */
int pll_update_configuration(void* pll_handle, uint8_t modulation_type);

/**
 * \brief  This function sets a flag to update the PLL configurations in case bandwidth or chirp-time or modulation changes.
 *
 * \param[in] flag  '0' for false and non-zero for true
 *
 */
void pll_set_update_config_flag(uint8_t flag);

/**
 * \brief  This function returns the PLL update configuration flag, used to check if a new PLL configuration is required.
 *
 * \return '0' for false and non-zero for true
 *
 */
uint8_t pll_get_update_config_flag(void);

/**
 * \brief This function sets the PLL base frequency.
 *
 * \param[in] freq_MHz  A double point value for the PLL base frequency, which should be within the limits of [24020 , 24240] MHz
 *
 */
void pll_set_frequency(double freq_MHz);

/**
 * \brief This function returns the current PLL base frequency.
 *
 * \return A floating point pointer for the PLL base frequency, which should be within the limits of [24020 , 24240] MHz
 *
 */
double pll_get_frequency(void);

/**
 * \brief This function sets the number of chirps count per frame.
 *
 * \param[in] num_chirps_per_frame  The number of chirps count per frame
 *
 */
void pll_set_num_chirps_per_frame(uint32_t num_chirps_per_frame);

/**
 * \brief This function sets the PLL upper and lower frequencies for FMCW modulation.
 *
 * \param[in] lower_freq_MHz  A double point value for the PLL lower frequency for FMCW modulation
 * \param[in] upper_freq_MHz  A double point value for the PLL upper frequency for FMCW modulation
 *
 */
void pll_set_upper_lower_frequency(double lower_freq_MHz, double upper_freq_MHz);

/**
 * \brief This function sets the PLL bandwidth in units of MHz.
 *
 * \param[in] bandwidth_MHz  The current bandwidth in units of MHz
 *
 */
void pll_set_bandwidth(float bandwidth_MHz);

/**
 * \brief This function sets the PLL chirp-time in units of microseconds.
 *
 * \param[in] chirp_time_usec	The current chirp-time in units of microseconds
 *
 */
void pll_set_chirp_time(uint32_t chirp_time_usec);

/* --- Close open blocks -------------------------------------------------- */

/* Disable C linkage for C++ files */
#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */

#endif 

/* --- End of File -------------------------------------------------------- */