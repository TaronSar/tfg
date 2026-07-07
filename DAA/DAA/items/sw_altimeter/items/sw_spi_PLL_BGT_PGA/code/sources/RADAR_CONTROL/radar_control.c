
/*
==============================================================================
   1. INCLUDE FILES
==============================================================================
 */
#include "radar_control.h"


int radar_set_pll_frequency( float freq_MHz);

void RF_set_num_chirps_per_frame(uint32_t num_chirps_per_frame);



int main(){

    int Status;
    int pll_modulation_mode;
    /* PLL parameters setup */
    /* -------------------- */
    float temp_pll_lower_freq_MHz = BSP_MIN_RF_FREQUENCY_KHZ / 1000.0f;
    float temp_pll_upper_freq_MHz = BSP_MAX_RF_FREQUENCY_KHZ / 1000.0f;
  
    /* Set PLL upper and lower frequencies for FMCW modulation */
    pll_set_upper_lower_frequency(temp_pll_lower_freq_MHz, temp_pll_upper_freq_MHz);
  
#if FW_MODULATION_TYPE == 1U
  
    pll_modulation_mode = MODULATION_FMCW;
    Status = radar_set_pll_frequency(temp_pll_upper_freq_MHz);

#endif
    /* Set the number of chirps count per frame */
    RF_set_num_chirps_per_frame(16);

    PS_RF_init();
}


int radar_set_pll_frequency( float freq_MHz)
{
  if ((freq_MHz >= BSP_MIN_RF_FREQUENCY_KHZ/1000.0f) && (freq_MHz <= BSP_MAX_RF_FREQUENCY_KHZ/1000.0f))
  {
    pll_set_frequency(freq_MHz);
    pll_set_update_config_flag(true);
    
    return (XST_SUCCESS);
  }
  else
  {
    return (XST_FAILURE);
  }
}

void RF_set_num_chirps_per_frame(uint32_t num_chirps_per_frame)
{
  pll_set_num_chirps_per_frame(num_chirps_per_frame);
}