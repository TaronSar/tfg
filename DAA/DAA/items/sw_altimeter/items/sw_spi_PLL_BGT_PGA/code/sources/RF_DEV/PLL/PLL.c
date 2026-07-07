/*
==============================================================================
   1. INCLUDE FILES
==============================================================================
 */

#include "PLL.h"
#include <stdbool.h>
/*
==============================================================================
   2. DEFINES
==============================================================================
 */

#define ISM_MIN_RF_FREQUENCY_KHZ     (24025000U)   /**< Minimum RF frequency supported by BGT24MTR1x in kHz */
#define ISM_MAX_RF_FREQUENCY_KHZ     (24225000U)   /**< Maximum RF frequency supported by BGT24MTR1x in kHz */

/*
==============================================================================
   3. DATA
==============================================================================
 */

static uint32_t s_pll_chirp_time_usec = DEFAULT_CHIRP_TIME_USEC; /* Current chirp-time in units of usec used by PLL */

static float s_pll_bandwidth_MHz = MAX_BANDWIDTH_MHZ; /* Current bandwidth in units of MHz used by PLL */

static float s_pll_lower_freq_MHz = 0; /* PLL lower frequency for FMCW modulation */

static float s_pll_upper_freq_MHz = 0; /* PLL upper frequency for FMCW modulation */

static uint32_t s_pll_num_of_chirps = 0; /* Number of chirps count per frame */

static float s_pll_base_freq_MHz = 0; /* PLL base frequency for Doppler and FMCW modulation */

static volatile  uint8_t  s_update_pll_config_flag = false; /* PLL SPI ramp settings if bandwidth, chirp-time and base frequency changes */

/*
==============================================================================
   3. EXPORTED FUNCTIONS
==============================================================================
 */
void pll_power_up(void)
{  /* PLL power-up */
	lmx249x_power_up();
}

void pll_power_down(void)
{  /* PLL power-down */
  lmx249x_power_down();
}

int pll_init(Lmx249x_Object_t* pll_handle,XSpiPs *SpiInstancePtr)
{
  int Status;
  //Lmx249x_Object_t* lmx249x_pll = (Lmx249x_Object_t*)pll_handle;
  Lmx249x_Hardware_Setup_t s_sPLLHardwareSetup;

  /* Send general configuration to PLL */
  /* --------------------------------- */
  s_sPLLHardwareSetup.dReferenceFreq         = 40.0;
  s_sPLLHardwareSetup.uReferenceDivider      = 1;
  s_sPLLHardwareSetup.eReferenceDoubler      = LMX249x_OSCIN_DOUBLER_OFF;
  s_sPLLHardwareSetup.eOscInMode             = LMX249x_OSCIN_SINGLE_ENDED;
  s_sPLLHardwareSetup.uExternalDivider       = 16;
  s_sPLLHardwareSetup.eTrig1PinFunction      = LMX249x_MUX_OUT_FLAG0_FROM_RAMP;
  s_sPLLHardwareSetup.eTrig1PinDriveMode     = LMX249x_PIN_FCN_PULLUPDN_OUT;
  s_sPLLHardwareSetup.eTrig2PinFunction      = LMX249x_MUX_IN_TRIG2;
  s_sPLLHardwareSetup.eTrig2PinDriveMode     = LMX249x_PIN_FCN_INPUT;
  s_sPLLHardwareSetup.eModPinFunction        = LMX249x_MUX_OUT_FLAG1_FROM_RAMP;
  s_sPLLHardwareSetup.eModPinDriveMode       = LMX249x_PIN_FCN_PULLUPDN_OUT;
  s_sPLLHardwareSetup.eMUXoutPinFunction     = LMX249x_MUX_OUT_READ_BACK;
  s_sPLLHardwareSetup.eMUXoutPinDriveMode    = LMX249x_PIN_FCN_PULLUPDN_OUT;
  s_sPLLHardwareSetup.eChargePumpPolarity    = LMX249x_CPPOL_NEGATIVE;
  s_sPLLHardwareSetup.uChargePumpCurrent     = 20;
  s_sPLLHardwareSetup.uChargePumpCurrentFS   = 0;
  s_sPLLHardwareSetup.uChargePumpThresholdLo = 6;
  s_sPLLHardwareSetup.uChargePumpThresholdHi = 42;
  s_sPLLHardwareSetup.eChargePumpPulseWidth  = LMX249x_CP_PULSE_860PS;
  s_sPLLHardwareSetup.eCycleSlipReduction    = LMX249x_CSR_DISABLED;
  s_sPLLHardwareSetup.uFastLockTimer         = 0;
  s_sPLLHardwareSetup.uLockDetectNumGoodEdge = 32;
  s_sPLLHardwareSetup.uLockDetectNumBadEdge  = 4;
  s_sPLLHardwareSetup.eLockDetectWindow      = LMX249x_DLD_TOL_10NS;

  s_sPLLHardwareSetup.SPI_devicePtr 	     = SpiInstancePtr;

  Status = lmx249x_init(pll_handle, &s_sPLLHardwareSetup, XSpiPs_PolledTransfer);
  	if (Status != XST_SUCCESS) {
    	xil_printf("Error 7\n");
    	Status = XST_FAILURE;
    	return Status;
    }

  lmx249x_set_power_state(pll_handle, LMX249x_POWER_CE);  
  return Status;
  //
}

int pll_update_configuration(void* pll_handle, uint8_t modulation_type)
{
  int Status;
  Lmx249x_Object_t* lmx249x_pll = (Lmx249x_Object_t*)pll_handle;

  pll_configure_ramps(lmx249x_pll);

  if (modulation_type == 1) /* FMCW modulation */
  {
    Status = lmx249x_enable_ramps(lmx249x_pll, true);
  }
  else
  {
    Status = lmx249x_set_frequency(lmx249x_pll, s_pll_base_freq_MHz, LMX249x_FRAC_ORD_THIRD, LMX249x_FRAC_DITHER_WEAK);
  }

  s_update_pll_config_flag = false;
  return Status;
}

void pll_configure_ramps(void* pll_handle)
{
  /* Setup data configuration data for PLL chip */
  Lmx249x_Object_t*	lmx249x_pll = (Lmx249x_Object_t*) pll_handle;

  Lmx249x_Ramp_Global_t pllGlobalRampSetup;

  Lmx249x_Ramp_Section_t pllRampSections[5];

  pllGlobalRampSetup.dBaseFrequency = (double)s_pll_base_freq_MHz; /*!< base frequency */

  pllGlobalRampSetup.dMinFrequency  = (double)(s_pll_lower_freq_MHz - (float)PLL_RAMP_GUARD_FREQ_MHZ); /*!< Minimum frequency that can't be underrun by a ramp */
  pllGlobalRampSetup.dMaxFrequency  = (double)(s_pll_upper_freq_MHz + (float)PLL_RAMP_GUARD_FREQ_MHZ); /*!< Maximum frequency that can't be overrun by a ramp */
  pllGlobalRampSetup.dComp0Freq     = (double)s_pll_lower_freq_MHz; /*!< Frequency that is used by Comparator 0 to compare the ramp with. */
  pllGlobalRampSetup.dComp1Freq     = (double)s_pll_upper_freq_MHz; /*!< Frequency that is used by Comparator 0 to compare the ramp with. */
  pllGlobalRampSetup.dDeviationFrequency = 0;  			    /*!< FSK deviation frequency */

  pllGlobalRampSetup.uNumRamps = s_pll_num_of_chirps * 4 + 1;	    /*!< Number of ramps to do before ramp is disabled (set to 0 for infinite number of ramps) */

  pllGlobalRampSetup.eTriggerA   = LMX249x_RAMP_TRIG_NEVER_TRIGGERS;             /*!< Define the source for Trigger A */
  pllGlobalRampSetup.eTriggerB   = LMX249x_RAMP_TRIG_TRIG2_TERMINAL_RISING_EDGE; /*!< Define the source for Trigger B */
  pllGlobalRampSetup.eTriggerC   = LMX249x_RAMP_TRIG_NEVER_TRIGGERS;             /*!< Define the source for Trigger C */
  pllGlobalRampSetup.eRampClock  = LMX249x_RAMP_CLOCK_INTERNAL;         	 /*!< determines if internal or external clock for ramp timing is used */
  pllGlobalRampSetup.eModulation = LMX249x_RAMP_MODULATION_FM;        		 /*!< Kind of modulation */
  pllGlobalRampSetup.eAutoOff    = LMX249x_RAMP_AUTO_OFF_ENABLE;           	 /*!< Defines, if the Ramp should be turned off after a certain amount of ramps */
  pllGlobalRampSetup.eRampCountTrigger = LMX249x_RAMP_COUNT_INCREMENT_SEGMENT_TRANSITION; /*!< Defines the increment trigger for the ramp counter */
  pllGlobalRampSetup.eDevTrigger = LMX249x_TRIGGER_A;				 /*!< Defines the deviation trigger for FSK operation */
  pllGlobalRampSetup.eDitherMode = LMX249x_FRAC_DITHER_DISABLED;                 /*!< Defines the fractional dithering */
  pllGlobalRampSetup.eFracOrder  = LMX249x_FRAC_ORD_SECOND;                      /*!< Defines the fractional order */

  /* Calculate real frequency shift based on PLL clock */
  double bandwidth_MHz = lmx249x_get_real_frequency_shift(lmx249x_pll, s_pll_bandwidth_MHz, s_pll_chirp_time_usec);

  /* reset ramp  */
  pllRampSections[0].dFreqShift   = 0.0;
  pllRampSections[0].eFastlock    = LMX249x_RAMP_FASTLOCK_DISABLED;
  pllRampSections[0].dTramp       = 0;
  pllRampSections[0].eFlag        = LMX249x_RAMP_FLAG_CLR_BOTH;
  pllRampSections[0].eReset       = LMX249x_RAMP_RST_ENABLE;
  pllRampSections[0].eNextTrig    = LMX249x_RAMP_NEXT_TRIG_TRIGB;
  pllRampSections[0].uNext        = 1;
  pllRampSections[0].eComparators = LMX249x_RAMP_NO_COMPARATOR;

  /* Ramp down to lower frequency */
  pllRampSections[1].dFreqShift   = -bandwidth_MHz;
  pllRampSections[1].eFastlock    = LMX249x_RAMP_FASTLOCK_DISABLED;
  pllRampSections[1].dTramp       = (double)PLL_RAMP_DOWM_TIME_USEC;
  pllRampSections[1].eFlag        = LMX249x_RAMP_FLAG_CLR_BOTH;
  pllRampSections[1].eReset       = LMX249x_RAMP_RST_DISABLE; /* first ramp resets counters */
  pllRampSections[1].eNextTrig    = LMX249x_RAMP_NEXT_TRIG_RAMPX_LEN;
  pllRampSections[1].uNext        = 2;
  pllRampSections[1].eComparators = LMX249x_RAMP_NO_COMPARATOR;

  /* Wait time between ramps */
  pllRampSections[2].dFreqShift   = 0;
  pllRampSections[2].eFastlock    = LMX249x_RAMP_FASTLOCK_DISABLED;
  pllRampSections[2].dTramp       = (double)PLL_STEADY_STATE_USEC;
  pllRampSections[2].eFlag        = LMX249x_RAMP_FLAG_CLR_BOTH;
  pllRampSections[2].eReset       = LMX249x_RAMP_RST_DISABLE;
  pllRampSections[2].eNextTrig    = LMX249x_RAMP_NEXT_TRIG_RAMPX_LEN;
  pllRampSections[2].uNext        = 3;
  pllRampSections[2].eComparators = LMX249x_RAMP_NO_COMPARATOR;

  /* Ramp up and trigger ADC sampling */
  pllRampSections[3].dFreqShift   = bandwidth_MHz;
  pllRampSections[3].eFastlock    = LMX249x_RAMP_FASTLOCK_DISABLED;
  pllRampSections[3].dTramp       = (double)s_pll_chirp_time_usec;
  pllRampSections[3].eFlag        = LMX249x_RAMP_FLAG_SET_BOTH;
  pllRampSections[3].eReset       = LMX249x_RAMP_RST_DISABLE;
  pllRampSections[3].eNextTrig    = LMX249x_RAMP_NEXT_TRIG_RAMPX_LEN;
  pllRampSections[3].uNext        = 4;
  pllRampSections[3].eComparators = LMX249x_RAMP_NO_COMPARATOR;

  /* Clear ADC sampling flags */
  pllRampSections[4].dFreqShift   = 0;
  pllRampSections[4].eFastlock    = LMX249x_RAMP_FASTLOCK_DISABLED;
  pllRampSections[4].dTramp       = 0;
  pllRampSections[4].eFlag        = LMX249x_RAMP_FLAG_CLR_BOTH;
  pllRampSections[4].eReset       = LMX249x_RAMP_RST_ENABLE;
  pllRampSections[4].eNextTrig    = LMX249x_RAMP_NEXT_TRIG_RAMPX_LEN;
  pllRampSections[4].uNext        = 1;
  pllRampSections[4].eComparators = LMX249x_RAMP_NO_COMPARATOR;

  lmx249x_configure_ramps(lmx249x_pll, &pllGlobalRampSetup, pllRampSections, 5);
}

int  pll_enable_ramps(void* pll_handle)
{ int Status;
  Lmx249x_Object_t* lmx249x_pll = (Lmx249x_Object_t*)pll_handle;
  Status = lmx249x_enable_ramps(lmx249x_pll, true);

  return Status;
}

//============================================================================

int pll_disable_ramps(void* pll_handle)
{ int Status;
  Lmx249x_Object_t* lmx249x_pll = (Lmx249x_Object_t*)pll_handle;
  Status = lmx249x_enable_ramps(lmx249x_pll, false);

  return Status;
}

//============================================================================

void pll_trigger_ramp(void)
{
  /* Start ramps generation */
  lmx249x_trigger_ramp();
}


void pll_set_update_config_flag(u8 flag)
{
  if (flag == 0)
  {
    s_update_pll_config_flag = false;
  }
  else
  {
    s_update_pll_config_flag = true;
  }
}

u8 pll_get_update_config_flag(void)
{
  return (s_update_pll_config_flag);
}

void pll_set_frequency(double freq_MHz)
{
	/* This check ensures, that the RF Frequency is not set out-side of the 24GHz- ISM band,
	 * do not circumvent it would understanding the consequences. Emitting outside ISM band is forbidden.
	 */

	if( freq_MHz < (double) ISM_MIN_RF_FREQUENCY_KHZ / 1000.0 )
		freq_MHz = (double) ISM_MIN_RF_FREQUENCY_KHZ / 1000.0;

	else if( freq_MHz > (double) ISM_MAX_RF_FREQUENCY_KHZ / 1000.0 )
		freq_MHz = (double) ISM_MAX_RF_FREQUENCY_KHZ / 1000.0;

	s_pll_base_freq_MHz = freq_MHz;
}

void pll_set_upper_lower_frequency(double lower_freq_MHz, double upper_freq_MHz)
{
	/* This check ensures, that the RF Frequency is not set out-side of the 24GHz- ISM band,
	 * do not circumvent it would understanding the consequences. Emitting outside ISM band is forbidden.
	 */
	if( lower_freq_MHz < (double) ISM_MIN_RF_FREQUENCY_KHZ / 1000.0 )
		lower_freq_MHz = (double) ISM_MIN_RF_FREQUENCY_KHZ / 1000.0;

	if( upper_freq_MHz > (double) ISM_MAX_RF_FREQUENCY_KHZ / 1000.0 )
		upper_freq_MHz = (double) ISM_MAX_RF_FREQUENCY_KHZ / 1000.0;

  s_pll_lower_freq_MHz = lower_freq_MHz;
  s_pll_upper_freq_MHz = upper_freq_MHz;
}

double pll_get_frequency(void)
{
  return(s_pll_base_freq_MHz);
}

void pll_set_num_chirps_per_frame(uint32_t num_chirps_per_frame)
{
  s_pll_num_of_chirps = num_chirps_per_frame;
}

void pll_set_bandwidth(float bandwidth_MHz)
{
  s_pll_bandwidth_MHz = bandwidth_MHz;
}

void pll_set_chirp_time(u32 chirp_time_usec)
{
  s_pll_chirp_time_usec = chirp_time_usec;
}
