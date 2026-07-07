/*
==============================================================================
   1. INCLUDE FILES
==============================================================================
 */

#include "LMX249x.h"

/*
==============================================================================
   2. EXPORTED FUNCTIONS
==============================================================================
 */
s32 lmx249x_init(Lmx249x_Object_t* pThis, const Lmx249x_Hardware_Setup_t* pSetup,
                  sendSPIFunction sendSPI)
{
  int Status;
  static u8 TXBuffer[17];
  static u8 RXBuffer[17];

  /* Set Internal Parameters */
  pThis->dExternalDivideFactor = (1.0 / pSetup->uExternalDivider); /* inverse RF-divider within the BGT chip */
  pThis->dPFDCycleTime = 1.0f / (pSetup->dReferenceFreq * (pSetup->eReferenceDoubler ? 2.0 : 1.0) / pSetup->uReferenceDivider );
  pThis->uReg58 = 0;
  pThis->SPI_devicePtr = pSetup->SPI_devicePtr;
  pThis->sendSPI = sendSPI;
  //pThis->pDataForSendSPI = pDataForSendSPI;

  /* Do Reset and set all PLL registers to the default value*/
  TXBuffer[0] = (u8) 0;
  TXBuffer[1] = (u8) 2;
  TXBuffer[2] = (u8) (1 << 2);

  //Status = XSpiPs_PolledTransfer((pThis->SPI_devicePtr), TXBuffer, RXBuffer,(u32) 3);
  //Send Data
  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 3);

  /* Setup Routing and Drive for Pins TRIG1, TRIG2, MOD and MUXout */
  TXBuffer[LMX249x_REG_IDX(25, 15, 35)] = 0x41 | /* these bits must be set */
      ((pSetup->eTrig1PinFunction      >> 2) & 0x08) | /* TRIG1_MUX[5] shifted to bit 3 */
        ((pSetup->eTrig2PinFunction   >> 1) & 0x10) | /* TRIG2_MUX[5] shifted to bit 4 */
          ((pSetup->eMUXoutPinFunction  >> 0) & 0x20) | /* MUXout_MUX[5] stays at bit 5 */
            ((pSetup->eModPinFunction     << 2) & 0x80);  /* MOD_MUX[5] shifted to at bit 7 */

  TXBuffer[LMX249x_REG_IDX(25, 15, 36)] = ((pSetup->eTrig1PinFunction  & 0x1F) << 3) | (pSetup->eTrig1PinDriveMode);

  TXBuffer[LMX249x_REG_IDX(25, 15, 37)] = ((pSetup->eTrig2PinFunction & 0x1F) << 3) |
      pSetup->eTrig2PinDriveMode;

  TXBuffer[LMX249x_REG_IDX(25, 15, 38)] = ((pSetup->eModPinFunction & 0x1F) << 3) |
      pSetup->eModPinDriveMode;

  TXBuffer[LMX249x_REG_IDX(25, 15, 39)] = ((pSetup->eMUXoutPinFunction & 0x1F) << 3) |
      pSetup->eMUXoutPinDriveMode;

    /* Setup Reference Scaling */
  TXBuffer[LMX249x_REG_IDX(25, 15, 25)] = (pSetup->uReferenceDivider >> 0) & 0xFF;
  TXBuffer[LMX249x_REG_IDX(25, 15, 26)] = (pSetup->uReferenceDivider >> 8) & 0xFF;
  TXBuffer[LMX249x_REG_IDX(25, 15, 27)] =  pSetup->eReferenceDoubler |
      (pSetup->eOscInMode << 2);

    /* Setup Charge Pump configuration */
  TXBuffer[LMX249x_REG_IDX(25, 15, 27)] |= (pSetup->eChargePumpPulseWidth << 3);
  TXBuffer[LMX249x_REG_IDX(25, 15, 28)] = ((pSetup->eChargePumpPolarity) << 5) |
      (pSetup->uChargePumpCurrent & 0x1F);
  TXBuffer[LMX249x_REG_IDX(25, 15, 29)] =  (pSetup->uChargePumpCurrentFS & 0x1F);

    /* Setup speed up settings */
  TXBuffer[LMX249x_REG_IDX(25, 15, 27)] |= (pSetup->eCycleSlipReduction << 5);
  TXBuffer[LMX249x_REG_IDX(25, 15, 32)]  = (pSetup->uFastLockTimer & 0xFF);
  TXBuffer[LMX249x_REG_IDX(25, 15, 29)] |= (pSetup->uFastLockTimer >> 3) & 0xE0;

    /* Setup lock detection */
  TXBuffer[LMX249x_REG_IDX(25, 15, 30)] =  pSetup->uChargePumpThresholdLo & 0x3F;
  TXBuffer[LMX249x_REG_IDX(25, 15, 31)] =  pSetup->uChargePumpThresholdHi & 0x3F;

  TXBuffer[LMX249x_REG_IDX(25, 15, 33)] =  pSetup->uLockDetectNumGoodEdge;
  TXBuffer[LMX249x_REG_IDX(25, 15, 34)] = (pSetup->uLockDetectNumBadEdge & 0x1F) |
      (pSetup->eLockDetectWindow << 5);

  TXBuffer[0] = 0;
  TXBuffer[1] = 25 + 15 - 1;

  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 15 + 2);
  xil_printf("Status_Transfer: %d\n\r",Status);
  return Status;
}

//============================================================================

s32 lmx249x_set_power_state(Lmx249x_Object_t* pThis, Lmx249x_Power_State_t eState)
{
	int Status;
	static u8 TXBuffer[3];
	static u8 RXBuffer[3];
	TXBuffer[0] = 0;
	TXBuffer[1] = 2;
	TXBuffer[2] = eState;
	Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 3);
	return Status;
}

Lmx249x_Error_Code_t lmx249x_set_frequency(Lmx249x_Object_t* pThis, double dBaseFrequency,
                                           Lmx249x_Frac_Order_t eFracOrder,
                                           Lmx249x_Frac_Dither_t eDitherMode)
{
  int Status;
  u8 TXBuffer[11]; /* Data buffer that will be passed to the SPI interface */
  u8 RXBuffer[11];
  double dRelFrequency;
  u32 iFactorN;
  u32 iFracDenominator;
  u32 iFracNumarator;

  /* Disable ramp (just in case a ramp is currently in progress) */
  TXBuffer[0] = 0;
  TXBuffer[1] = 58;
  TXBuffer[2] = 0;
  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 3);

  /* Setup frequency */
  dRelFrequency = dBaseFrequency * pThis->dExternalDivideFactor * pThis->dPFDCycleTime;  /* divider ratio between PLL-RF-in and PFD-frequency */

  iFactorN = (int32_t)dRelFrequency;
  dRelFrequency -= iFactorN;
  iFracDenominator = 1<<24;
  iFracNumarator = (u32)(dRelFrequency * iFracDenominator + 0.5);

  TXBuffer[LMX249x_REG_IDX(16, 9, 16)] = (int8_t) ((iFactorN >>  0) & 0xFF);
  TXBuffer[LMX249x_REG_IDX(16, 9, 17)] = (int8_t) ((iFactorN >>  8) & 0xFF);
  TXBuffer[LMX249x_REG_IDX(16, 9, 18)] = (int8_t) ((iFactorN >> 16) & 0x03) |
    (eFracOrder << 4)        |
      (eDitherMode << 2);

  TXBuffer[LMX249x_REG_IDX(16, 9, 19)] = (iFracNumarator >>  0) & 0xFF;
  TXBuffer[LMX249x_REG_IDX(16, 9, 20)] = (iFracNumarator >>  8) & 0xFF;
  TXBuffer[LMX249x_REG_IDX(16, 9, 21)] = (iFracNumarator >> 16) & 0xFF;

  iFracDenominator -= 1;
  TXBuffer[LMX249x_REG_IDX(16, 9, 22)] = (iFracDenominator >>  0) & 0xFF;
  TXBuffer[LMX249x_REG_IDX(16, 9, 23)] = (iFracDenominator >>  8) & 0xFF;
  TXBuffer[LMX249x_REG_IDX(16, 9, 24)] = (iFracDenominator >> 16) & 0xFF;

  /* Send register sequence to PLL */
  TXBuffer[0] = 0;
  TXBuffer[1] = 16 + 9 - 1;
  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 9+2);

  return (Status);
}


void lmx249x_power_up(void)
{
	xil_printf("Status prendido: \n\r");
    DIGITAL_IO_SetOutputHigh(&DIGITAL_IO_PLL_CE);
}

void lmx249x_power_down(void)
{
  DIGITAL_IO_SetOutputLow(&DIGITAL_IO_PLL_CE);
}

int lmx249x_enable_ramps(Lmx249x_Object_t* pThis, u8 bEnable)
{
  int Status;
  u8 TXBuffer[4];
  u8 RXBuffer[4];

  TXBuffer[0] = 0;              /* High address byte */
  TXBuffer[1] = 58;             /* Low address byte */
  TXBuffer[2] = pThis->uReg58;  /* Configuration of register 58 */

  /* enable ramps */
  if (bEnable != 0)
	  TXBuffer[2] |= 1;
  else
	  TXBuffer[2] &= 0xFE;

  //pThis->sendSPI(TXBuffer, 3, pThis->pDataForSendSPI);
  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 3);

  return Status;
}

Lmx249x_Error_Code_t lmx249x_configure_ramps(Lmx249x_Object_t* pThis,
                                             const Lmx249x_Ramp_Global_t* pGlobalSettings,
                                             const Lmx249x_Ramp_Section_t* pRampSections,
                                             u8 uNumSections)
{
	  int Status;
	  u8 TXBuffer[29];  /* Data buffer that will be passed to the SPI interface */
	  u8 RXBuffer[29];
	  const double dFrequencyToNFactor = pThis->dExternalDivideFactor * pThis->dPFDCycleTime;
	  const double dFracDenominator = (double)(1<<24);
	  u8 uComparator0Enable = 0;
	  u8 uComparator1Enable = 0;
	  int8_t uIdx;
	  uint16_t uBaseRegister;
	  const u8 uNumRegs = 7;
	  const Lmx249x_Ramp_Section_t* pThisSection;
	  u32 uRampLength;
	  u8 uDelayFlag = 0;
	  u32 uCounterInc;
	  u8 uCompEnMask;
	  double dRelFrequency;
	  u32 iFactorN;
	  u32 iFracNumarator;
	  u64 iRampComp0;
	  u64 iRampComp1;
	  u64 iRampLimitLow;
	  u64 iRampLimitHigh;
	  u64 iFSKDev;

	  /* Check if the number of range is in a valid range */
	  if ((uNumSections < 1) || (uNumSections > 8))
	    return (LMX249x_ERROR_CODE_INVALID_NUMBER_OF_RAMPS);

	  /* Disable ramp (just in case a ramp is currently in progress) */
	  TXBuffer[0] = 0;
	  TXBuffer[1] = 58;
	  TXBuffer[2] = 0;
	  //pThis->sendSPI(TXBuffer, 3, pThis->pDataForSendSPI);
	  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 3);

	  /* Setup up the ramp sections */
	  for (uIdx = 0; uIdx < uNumSections; ++uIdx)
	  {
	    /* Setup register buffer */
	    uBaseRegister = (86 + uIdx * 7);
	    pThisSection = &pRampSections[uIdx];

	    /* Convert given ramp parameters to counter values */
	    uRampLength =  (int32_t) ((pThisSection->dTramp) / pThis->dPFDCycleTime);
	    if (uRampLength > 0xFFFF)
	    {
	      /* If the ramp is too long, divide ramp length by two and set the delay flag which doubles the ramp time */
	      uRampLength >>= 1;
	      uDelayFlag = 0x80;
	    }

	    /* If the transition to the next sections is triggered by the length of this section, the length must be
	    * at least 1, otherwise the counter seems to wrap around and the section will be longer than expected.
	    */
	    if ((uRampLength == 0) && (pThisSection->eNextTrig == LMX249x_RAMP_NEXT_TRIG_RAMPX_LEN))
	      uRampLength = 1;

	    uCounterInc =  (int32_t) (pThisSection->dFreqShift * dFrequencyToNFactor * dFracDenominator / (double)uRampLength);

	    /* Set ramp_increment */
	    TXBuffer[LMX249x_REG_IDX(0, uNumRegs, 0)] = (u8) ((uCounterInc >>  0) & 0xFF);
	    TXBuffer[LMX249x_REG_IDX(0, uNumRegs, 1)] = (u8) ((uCounterInc >>  8) & 0xFF);
	    TXBuffer[LMX249x_REG_IDX(0, uNumRegs, 2)] = (u8) ((uCounterInc >> 16) & 0xFF);

	    /* Set flags and increment */
	    TXBuffer[LMX249x_REG_IDX(0, uNumRegs, 3)] = uDelayFlag |
	      (u8) ((pThisSection->eFastlock) << 6) |
	        (u8) ((uCounterInc >> 24) & 0x3F);

	    /* Set ramp_length */
	    TXBuffer[LMX249x_REG_IDX(0, uNumRegs, 4)] = ((uRampLength >> 0) & 0xFF);
	    TXBuffer[LMX249x_REG_IDX(0, uNumRegs, 5)] = ((uRampLength >> 8) & 0xFF);

	    /* Set flags */
	    TXBuffer[LMX249x_REG_IDX(0, uNumRegs, 6)] = ((int8_t) ((pThisSection->uNext &0x07)  << 5)) |
	      ((int8_t)  (pThisSection->eNextTrig << 3)) |
	        ((int8_t)  (pThisSection->eReset    << 2)) |
	          ((int8_t)  (pThisSection->eFlag   << 0));

	    /* Set comparator enable bit */
	    uCompEnMask = 1 << uIdx;
	    uComparator0Enable |= (pThisSection->eComparators & LMX249x_RAMP_USE_COMPARATOR_1) ? uCompEnMask : 0;
	    uComparator1Enable |= (pThisSection->eComparators & LMX249x_RAMP_USE_COMPARATOR_1) ? uCompEnMask : 0;

	    /* Write the register data to the chip, write highest address (the one of the register written first) at the
	    * beginning of the data buffer.
	    */
	    uBaseRegister += uNumRegs - 1;
	    TXBuffer[0] = (u8)((uBaseRegister >> 8) & 0xFF);
	    TXBuffer[1] = (u8)((uBaseRegister >> 0) & 0xFF);
	    //pThis->sendSPI(TXBuffer, uNumRegs + 2, pThis->pDataForSendSPI);
	    Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) uNumRegs + 2);
	  	}

	  /* Wet comparator enable bits */
	  TXBuffer[LMX249x_REG_IDX(58, 27, 64)] = uComparator0Enable;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 69)] = uComparator1Enable;

	  /* Setup base frequency */
	  dRelFrequency = pGlobalSettings->dBaseFrequency * dFrequencyToNFactor;  /* divider ratio between PLL-RF-in and PFD-frequency */

	  iFactorN = (int32_t)dRelFrequency;
	  dRelFrequency -= iFactorN;
	  iFracNumarator = (uint32_t) (dRelFrequency * dFracDenominator);

	  TXBuffer[LMX249x_REG_IDX(16, 9, 16)] = (int8_t) ((iFactorN >>  0) & 0xFF);
	  TXBuffer[LMX249x_REG_IDX(16, 9, 17)] = (int8_t) ((iFactorN >>  8) & 0xFF);

	  TXBuffer[LMX249x_REG_IDX(16, 9, 18)] = (int8_t) (((iFactorN >> 16) & 0x03) | (pGlobalSettings->eFracOrder << 4) | (pGlobalSettings->eDitherMode << 2));

	  TXBuffer[LMX249x_REG_IDX(16, 9, 19)] = (iFracNumarator >>  0) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(16, 9, 20)] = (iFracNumarator >>  8) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(16, 9, 21)] = (iFracNumarator >> 16) & 0xFF;


	  /* Fractional denominator is always 0xFFFFFF when ramp generator is active */
	  TXBuffer[LMX249x_REG_IDX(16, 9, 22)] = 0xFF;
	  TXBuffer[LMX249x_REG_IDX(16, 9, 23)] = 0xFF;
	  TXBuffer[LMX249x_REG_IDX(16, 9, 24)] = 0xFF;

	  /*Send register sequence to PLL */
	  TXBuffer[0] = 0;
	  TXBuffer[1] = 16 + 9 - 1;

	  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32)  9 + 2);

	  /* Setup ramp range and comparator values */
	  /* The formula in the LMX249x data sheet for the following settings is very misleading. The used formular was
	  * found by debugging. The essence here is to specify the limits as the difference (limFreq - baseFreq), while
	  * limFreq is the N factor with fractional part, but baseFreq must be the integer N factor (no rounding, just truncating).
	  */
	  iRampComp0     = (int64_t) ((pGlobalSettings->dComp0Freq    * dFrequencyToNFactor - iFactorN) * dFracDenominator);
	  iRampComp1     = (int64_t) ((pGlobalSettings->dComp1Freq    * dFrequencyToNFactor - iFactorN) * dFracDenominator);
	  iRampLimitLow  = (int64_t) ((pGlobalSettings->dMinFrequency * dFrequencyToNFactor - iFactorN) * dFracDenominator);
	  iRampLimitHigh = (int64_t) ((pGlobalSettings->dMaxFrequency * dFrequencyToNFactor - iFactorN) * dFracDenominator);

	  TXBuffer[LMX249x_REG_IDX(58, 27, 60)] = (iRampComp0 >>  0) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 61)] = (iRampComp0 >>  8) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 62)] = (iRampComp0 >> 16) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 63)] = (iRampComp0 >> 24) & 0xFF;

	  TXBuffer[LMX249x_REG_IDX(58, 27, 65)] = (iRampComp1 >>  0) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 66)] = (iRampComp1 >>  8) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 67)] = (iRampComp1 >> 16) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 68)] = (iRampComp1 >> 24) & 0xFF;

	  TXBuffer[LMX249x_REG_IDX(58, 27, 75)] = (iRampLimitLow >>  0) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 76)] = (iRampLimitLow >>  8) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 77)] = (iRampLimitLow >> 16) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 78)] = (iRampLimitLow >> 24) & 0xFF;

	  TXBuffer[LMX249x_REG_IDX(58, 27, 79)] = (iRampLimitHigh >>  0) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 80)] = (iRampLimitHigh >>  8) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 81)] = (iRampLimitHigh >> 16) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 82)] = (iRampLimitHigh >> 24) & 0xFF;

	  TXBuffer[LMX249x_REG_IDX(58, 27, 70)] = ((iRampComp0    & 0x100000000) ? 1 << 0 : 0) |
	    ((iRampComp1    & 0x100000000) ? 1 << 1 : 0) |
	      ((iRampLimitLow   & 0x100000000) ? 1 << 3 : 0) |
	        ((iRampLimitHigh  & 0x100000000) ? 1 << 4 : 0);

	  /* Define FSK deviation */
	  iFSKDev = (int64_t) ((pGlobalSettings->dDeviationFrequency - pGlobalSettings->dBaseFrequency)
	                       * dFrequencyToNFactor * (1 << 24));

	  TXBuffer[LMX249x_REG_IDX(58, 27, 71)] = (iFSKDev >>  0) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 72)] = (iFSKDev >>  8) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 73)] = (iFSKDev >> 16) & 0xFF;
	  TXBuffer[LMX249x_REG_IDX(58, 27, 74)] = (iFSKDev >> 24) & 0xFF;

	  TXBuffer[LMX249x_REG_IDX(58, 27, 70)] |= ((iFSKDev    & 0x100000000) ? 1 << 2 : 0)
	    | (pGlobalSettings->eDevTrigger << 5);

	  /* Define Ramp Trigger Sources and Modulation type */
	  pThis->uReg58 = (pGlobalSettings->eRampClock) /* 0 << 1) */  | /* internal or external clock */
	    (pGlobalSettings->eModulation) /* 0 << 2) */ | /* phase or frequency modulation */
	      (pGlobalSettings->eTriggerA << 4);          /* Trigger A source */
	  TXBuffer[LMX249x_REG_IDX(58, 27, 58)] = pThis->uReg58;

	  TXBuffer[LMX249x_REG_IDX(58, 27, 59)] = (pGlobalSettings->eTriggerB)   | /* Trigger B source */
	    (pGlobalSettings->eTriggerC << 4);   /* Trigger C source */

	  /* Setup ramp counter */
	  TXBuffer[LMX249x_REG_IDX(58, 27, 83)] = (pGlobalSettings->uNumRamps & 0xFF);
	  TXBuffer[LMX249x_REG_IDX(58, 27, 84)] = ((pGlobalSettings->uNumRamps >> 8)& 0x1F)  |
	    (pGlobalSettings->eAutoOff << 5)     |
	      (pGlobalSettings->eRampCountTrigger << 6);

	  xil_printf("valor de Tx_buffer[3]: %d\r\n",TXBuffer[3]);
	  /* Send register sequence to PLL */
	  TXBuffer[0] = 0;
	  TXBuffer[1] = 58 + 27 - 1;
	  Status = pThis->sendSPI((pThis->SPI_devicePtr),TXBuffer, RXBuffer,(u32) 27 + 2);

	  return (Status);
}

void lmx249x_trigger_ramp(void)
{
  /* Wait until PLL is ready to generate the next chirp */
  while (DIGITAL_IO_GetInput(&DIGITAL_IO_PLL_MOD) != 0);

  /* Start the chirp */
  DIGITAL_IO_SetOutputHigh(&DIGITAL_IO_PLL_TRIG2);
}

void lmx249x_release_ramp_trigger(void)
{
  DIGITAL_IO_SetOutputLow(&DIGITAL_IO_PLL_TRIG2);
}

double lmx249x_get_real_frequency_shift(Lmx249x_Object_t* pThis, double FreqShift_MHz, u32 FreqShift_time_usec)
{
  double RealFreqShift;
  const double FracDenominator = (double)(1<<24);
  u32 FreqShiftSteps;
  double FreqShiftPerStep;

  FreqShiftSteps =  (u32) (FreqShift_time_usec / pThis->dPFDCycleTime);

  FreqShiftPerStep = (FreqShift_MHz * pThis->dExternalDivideFactor) / FreqShiftSteps;

  FreqShiftPerStep = ((u32)((FreqShiftPerStep * FracDenominator) * pThis->dPFDCycleTime) ) / FracDenominator / pThis->dPFDCycleTime;

  RealFreqShift = FreqShiftPerStep * FreqShiftSteps /  pThis->dExternalDivideFactor;

  return (RealFreqShift);
}
/* --- End of File -------------------------------------------------------- */