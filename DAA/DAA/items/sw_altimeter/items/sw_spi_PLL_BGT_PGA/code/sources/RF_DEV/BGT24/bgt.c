
/*
==============================================================================
   1. INCLUDE FILES
==============================================================================
 */
#include "bgt.h"


/*
==============================================================================
   2. EXPORTED FUNCTIONS
==============================================================================
 */
void bgt_init(BGT_Object* txrx_handle, Bgt24mtr1x_LNAgain_t lna_gain, Bgt24mtr1x_Power_t tx_power, XSpiPs* Spi_Pointer)
{
	txrx_handle->LNAgain       	= lna_gain;
  txrx_handle->Power_Tx		= tx_power;
  txrx_handle->SPI_Ptr_bgt    = Spi_Pointer;

  bgt24mtr1x_init( txrx_handle->LNAgain, txrx_handle->Power_Tx);
  bgt24mtr1x_ana_vref_tx();
}

void bgt_start_tx(BGT_Object* txrx_handle)
{
  bgt24mtr1x_start_tx(txrx_handle);
}

//============================================================================

void bgt_stop_tx(BGT_Object* txrx_handle)
{
  bgt24mtr1x_stop_tx(txrx_handle);
}

//============================================================================

void bgt_power_up(void)
{
  /* CE pin is active low, so it should keep high until it is activated.
   */
  bgt24mtr1x_power_up();
  DIGITAL_IO_SetOutputLow(&DIGITAL_IO_BGT_POWER_ENA);
}

//============================================================================

void bgt_power_down(void)
{
  /* After turning off BGT, we should keep SPI's signals low
   * to avoid offset voltage at BGT's VCC.
   *
   * If they are above 0.3V which is bias voltage inside BGT, then inside BGT turns on.
   * It makes offset voltage at BGT's VCC.
   */
  DIGITAL_IO_SetOutputHigh(&DIGITAL_IO_BGT_POWER_ENA);

}

//============================================================================

uint8_t bgt_get_tx_power(void)
{
  return bgt24mtr1x_get_tx_power();
}

//============================================================================

void bgt_lna_gain_enable(void)
{
  bgt24mtr1x_lna_gain_enable();
}

//============================================================================

void bgt_lna_gain_disable(void)
{
  bgt24mtr1x_lna_gain_disable();
}

//============================================================================

uint8_t bgt_lna_gain_is_enable(void)
{
  return bgt24mtr1x_lna_gain_is_enable();
}

//============================================================================

void bgt_set_config( XSpiPs *SpiInstancePtr, uint16_t config_val)
{
  bgt24mtr1x_set_config( SpiInstancePtr,config_val);
}

//============================================================================

uint16_t bgt_get_config(void)
{
  return bgt24mtr1x_get_config();
}

//============================================================================

void bgt_ana_temp(void)
{
  bgt24mtr1x_ana_temp();
}

//============================================================================

void bgt_ana_vout_tx(void)
{
  bgt24mtr1x_ana_vout_tx();
}

//============================================================================

void bgt_ana_vref_tx(void)
{
  bgt24mtr1x_ana_vref_tx();
}

//============================================================================

uint16_t bgt_get_ana_config(void)
{
  return bgt24mtr1x_get_ana_config();
}

//============================================================================

void bgt_lowest_power_with_q2_disable(BGT_Object* txrx_handle)
{
  bgt24mtr1x_set_config(txrx_handle->SPI_Ptr_bgt ,(uint16_t)BGT24MTR1X_POWER_CONF);
}

//============================================================================

void bgt_ldo_enable()
{
  DIGITAL_IO_SetOutputHigh(&DIGITAL_IO_BGT_LDO_ENA);
}

//============================================================================

void bgt_ldo_disable(void)
{
  DIGITAL_IO_SetOutputLow(&DIGITAL_IO_BGT_LDO_ENA);
}

/* --- End of File -------------------------------------------------------- */
