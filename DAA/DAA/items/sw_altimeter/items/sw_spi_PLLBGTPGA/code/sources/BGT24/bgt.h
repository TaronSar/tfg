#ifndef BGT_H_
#define BGT_H_

/* Enable C linkage if header is included in C++ files */
#ifdef __cplusplus
extern "C"
{
#endif /* __cplusplus */

/*
==============================================================================
   1. INCLUDE FUNCTION
==============================================================================
 */
#include <stdio.h>
#include <stdbool.h>
#include "../SPI/SPI_device.h"
#include "bgt24mtr1x.h"
/*
==============================================================================
   2. EXPORTED FUNCTIONS
==============================================================================
 */

/**
 * \brief   This function initializes the BGT24MTR1x 16-bit SPI shadow register and send BGT settings.
 *        	RX LNA enable or disable settings and TX out put power level are also set in this function.
 */
void bgt_init(BGT_Object* txrx_handle, Bgt24mtr1x_LNAgain_t lna_gain, Bgt24mtr1x_Power_t tx_power, XSpiPs* Spi_Pointer);

/**
 * \brief 	This function enables BGT24MTR1x TX Power amplifier to start transmission.
 *			12th bit of SPI shadow register in BGT24MTR1x is enabled (high).
 */
void bgt_start_tx(BGT_Object* txrx_handle);

/**
 * \brief   This function disables BGT TX Power amplifier.
 */
void bgt_stop_tx(BGT_Object* txrx_handle);

/**
 * \brief   This function is used to power-up the BGT.
 */
void bgt_power_up(void);

/**
 * \brief   This function is used to power-down the BGT.
 */
void bgt_power_down(void);

/**
 * \brief   This function sets the power level [0- 7] of BGT24MTR1x TX Power amplifier.
 */
void bgt_set_tx_power(uint8_t power_level);

/**
 * \brief 	This function returns the power level [0 - 7] of BGT24MTR1x TX Power amplifier.
 */
uint8_t bgt_get_tx_power(void);

/**
 * \brief   This function enables the Receiver LNA gain.
 */
void bgt_lna_gain_enable(void);

/**
 * \brief   This function disables the Receiver LNA gain.
 */
void bgt_lna_gain_disable(void);

/**
 * \brief   This function returns the current status of the Receiver LNA gain, if enabled it returns true else false.
 */
uint8_t bgt_lna_gain_is_enable(void);

/**
 * \brief   This function transmits the 16-bit SPI settings to BGT24MTR1x registers \ref bgt24mtr1x_global_config.
 */
void bgt_set_config(XSpiPs *SpiInstancePtr, uint16_t config_val);

/**
 * \brief   This function transmits the 16-bit SPI settings to BGT24MTR1x registers \ref bgt24mtr1x_global_config.
 */
uint16_t bgt_get_config(void);

/**
 * \brief   This function sets the SPI settings for BGT24MTR1x to read the temperature output from AMUX pin.
 */
void bgt_ana_temp(void);

/**
 * \brief   This function sets the SPI settings for BGT24MTR1x to read the output TX power from AMUX pin.
 */
void bgt_ana_vout_tx(void);

/**
 * \brief   This function sets the SPI settings for BGT24MTR1x to read the reference TX power from AMUX pin.
 */
void bgt_ana_vref_tx(void);

/**
 * \brief   This function returns the current settings for Analog output defined by \ref bgt24mtr1x_ana_command.
 */
uint16_t bgt_get_ana_config(void);

/**
 * \brief   This function sets the lowest power with q2 disable for BGT.
 */
void bgt_lowest_power_with_q2_disable(BGT_Object* txrx_handle);

/**
 * \brief   This function enables the LDO for BGT.
 */
void bgt_ldo_enable(void);

/**
 * \brief   This function disables the LDO for BGT.
 */
void bgt_ldo_disable(void);

/* --- Close open blocks -------------------------------------------------- */

/* Disable C linkage for C++ files */
#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */

#endif /* BGT_H_ */

/* --- End of File -------------------------------------------------------- */
