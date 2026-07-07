#ifndef LMX249X_H_
#define LMX249X_H_

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
//
#include "xspips.h"
#include <stdint.h>
#include "../../PS_DRIVERs/DIGITAL_IO/digital_io.h"
#include "../../PS_DRIVERs/SPI/SPI_device.h"

/*
==============================================================================
   2. DEFINITIONS
==============================================================================
 */

/**
 * This Macro is an internal helper to calculate the correct register index when
 * writing a sequence of registers to the PLL. The register sequence is inverted
 * and shifted by 2 to reserve two bytes for the address at the beginning of the
 * data buffer.
 */
#define LMX249x_REG_IDX(BASE_REG, NUM_REGS, IDX)  ((NUM_REGS) - ((IDX)-(BASE_REG)) - 1 + 2)


/*
==============================================================================
   3. TYPES
==============================================================================
 */

/**
 * \brief Determines what event is necessary to cause the state machine to go to the next ramp.
 *        It can be set to when the RAMPx_LEN counter reaches zero or one of the events for Triggers A,B, or C.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_NEXT_TRIG_RAMPX_LEN                 = 0U,
  LMX249x_RAMP_NEXT_TRIG_TRIGA                     = 1U,
  LMX249x_RAMP_NEXT_TRIG_TRIGB                     = 2U,
  LMX249x_RAMP_NEXT_TRIG_TRIGC                     = 3U
} Lmx249x_Ramp_Next_Trig_t;
/** @} */

typedef enum
{
  LMX249x_RAMP_COUNT_INCREMENT_SEGMENT_TRANSITION  = 0U,
  LMX249x_RAMP_COUNT_INCREMENT_TRIG_TRIGA          = 1U,
  LMX249x_RAMP_COUNT_INCREMENT_TRIG_TRIGB          = 2U,
  LMX249x_RAMP_COUNT_INCREMENT_TRIG_TRIGC          = 3U
} Lmx249x_Ramp_Trig_Inc_t;
/** @} */

/**
 * \brief LMX249x Ramp reset.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_RST_DISABLE                         = 0U,
  LMX249x_RAMP_RST_ENABLE                          = 1U
} Lmx249x_Ramp_Reset_t;
/** @} */

/**
 * \brief LMX249x Ramp flags.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_FLAG_CLR_BOTH                       = 0U,
  LMX249x_RAMP_FLAG_SET_FLAG0_CLR_FLAG1            = 1U,
  LMX249x_RAMP_FLAG_SET_FLAG1_CLR_FLAG0            = 2U,
  LMX249x_RAMP_FLAG_SET_BOTH                       = 3U
} Lmx249x_Ramp_Flag_t;
/** @} */

/**
 * \brief LMX249x Ramp fast-lock enable.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_FASTLOCK_DISABLED                   = 0U,    /**< Disable fast-lock on a specific ramp */
  LMX249x_RAMP_FASTLOCK_ENABLED                    = 1U     /**< Enable fast-lock on a specific ramp */
} Lmx249x_Ramp_Fast_Lock_t;
/** @} */

/**
 * \brief LMX249x Ramp Comparators.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_NO_COMPARATOR                       = 0U,
  LMX249x_RAMP_USE_COMPARATOR_0                    = 1U,
  LMX249x_RAMP_USE_COMPARATOR_1                    = 2U,
  LMX249x_RAMP_USE_BOTH_COMPARATORS                = 3U
} Lmx249x_Ramp_Comparators_t;
/** @} */

/**
 * \brief LMX249x Ramp trigger definitions.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_TRIG_NEVER_TRIGGERS                 = 0U,
  LMX249x_RAMP_TRIG_TRIG1_TERMINAL_RISING_EDGE     = 1U,
  LMX249x_RAMP_TRIG_TRIG2_TERMINAL_RISING_EDGE     = 2U,
  LMX249x_RAMP_TRIG_MOD_TERMINAL_RISING_EDGE       = 3U,
  LMX249x_RAMP_TRIG_DLD_RISING_EDGE                = 4U,
  LMX249x_RAMP_TRIG_CMP0_DETECTED_LEVEL            = 5U,
  LMX249x_RAMP_TRIG_RAMPX_CPG_RISING_EDGE          = 6U,
  LMX249x_RAMP_TRIG_RAMPX_FLAG0_RISING_EDGE        = 7U,
  LMX249x_RAMP_TRIG_ALWAYS_TRIGGERED_LEVEL         = 8U,
  LMX249x_RAMP_TRIG_TRIG1_TERMINAL_FALLING_EDGE    = 9U,
  LMX249x_RAMP_TRIG_TRIG2_TERMINAL_FALLING_EDGE    = 10U,
  LMX249x_RAMP_TRIG_MOD_TERMINAL_FALLING_EDGE      = 11U,
  LMX249x_RAMP_TRIG_DLD_FALLING_EDGE               = 12U,
  LMX249x_RAMP_TRIG_CMP1_DETECTED_LEVEL            = 13U,
  LMX249x_RAMP_TRIG_RAMPX_CPG_FALLING_EDGE         = 14U,
  LMX249x_RAMP_TRIG_RAMPX_FLAG0_FALLING_EDGE       = 15U
} Lmx249x_Ramp_Trigger_Source_t;
/** @} */

/**
 * \brief LMX249x Clock Source for ramp length control.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_CLOCK_INTERNAL                      = 0U,    /**< Ramp clock derived from the phase detector */
  LMX249x_RAMP_CLOCK_EXTERNAL                      = 1U     /**< Clock derived from MOD-Terminal */
} Lmx249x_Ramp_Clock_t;
/** @} */

/**
 * \brief LMX249x ramp modulation control.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_MODULATION_FM                       = 0U,    /**< Enable Frequency Modulation */
  LMX249x_RAMP_MODULTAION_PM                       = 1U     /**< Enable Phase Modulation */
} Lmx249x_Ramp_Modulation_t;
/** @} */

/**
 * \brief LMX249x FSK trigger type.
 * @{
 */
typedef enum
{
  LMX249x_TRIGGER_ALWAYS                           = 0U,    /**< FSK Deviation is always applied */
  LMX249x_TRIGGER_A                                = 1U,    /**< FSK Deviation is triggered by Trigger A */
  LMX249x_TRIGGER_B                                = 2U,    /**< FSK Deviation is triggered by Trigger B */
  LMX249x_TRIGGER_C                                = 3U     /**< FSK Deviation is triggered by Trigger C */
} Lmx249x_Trigger_Select_t;
/** @} */

/**
 * \brief LMX249x Ramp auto mode.
 * @{
 */
typedef enum
{
  LMX249x_RAMP_AUTO_OFF_DISABLE                    = 0U,    /**< Ramp continues regardless of the ramp counter */
  LMX249x_RAMP_AUTO_OFF_ENABLE                     = 1U     /**< Ramp is turned off after a certain number of ramps */
} Lmx249x_Ramp_AutoOff_t;
/** @} */

/**
 * \brief LMX249x fractional order.
 * @{
 */
typedef enum
{
  LMX249x_FRAC_ORD_INT                             = 0U,
  LMX249x_FRAC_ORD_FIRST                           = 1U,
  LMX249x_FRAC_ORD_SECOND                          = 2U,
  LMX249x_FRAC_ORD_THIRD                           = 3U,
  LMX249x_FRAC_ORD_FOURTH                          = 4U
} Lmx249x_Frac_Order_t;
/** @} */

/**
 * \brief LMX249x fractional dithering.
 * @{
 */
typedef enum
{
  LMX249x_FRAC_DITHER_WEAK                         = 0U,
  LMX249x_FRAC_DITHER_MEAN                         = 1U,
  LMX249x_FRAC_DITHER_STRONG                       = 2U,
  LMX249x_FRAC_DITHER_DISABLED                     = 3U
} Lmx249x_Frac_Dither_t;
/** @} */

/**
 * \brief LMX249x MUX functions for pins.
 * @{
 */
typedef enum
{
  LMX249x_MUX_GND                                  = 0U,
  LMX249x_MUX_IN_TRIG1                             = 1U,
  LMX249x_MUX_IN_TRIG2                             = 2U,
  LMX249x_MUX_IN_MOD                               = 3U,
  LMX249x_MUX_OUT_TRIG1_AFTER_SYNC                 = 4U,
  LMX249x_MUX_OUT_TRIG2_AFTER_SYNC                 = 5U,
  LMX249x_MUX_OUT_MOD_AFTER_SYNC                   = 6U,
  LMX249x_MUX_OUT_READ_BACK                        = 7U,
  LMX249x_MUX_OUT_CMP0                             = 8U,
  LMX249x_MUX_OUT_CMP1                             = 9U,
  LMX249x_MUX_OUT_LD                               = 10U,
  LMX249x_MUX_OUT_DLD                              = 11U,
  LMX249x_MUX_OUT_CPMON_GOOD                       = 12U,
  LMX249x_MUX_OUT_CPMON_TOO_HIGH                   = 13U,
  LMX249x_MUX_OUT_CPMON_TOO_LOW                    = 14U,
  LMX249x_MUX_OUT_RAMP_LIMIT_EXCEEDED              = 15U,
  LMX249x_MUX_OUT_R_DIVIDE_BY_2                    = 16U,
  LMX249x_MUX_OUT_R_DIVIDE_BY_4                    = 17U,
  LMX249x_MUX_OUT_N_DIVIDE_BY_2                    = 18U,
  LMX249x_MUX_OUT_N_DIVIDE_BY_4                    = 19U,
  LMX249x_MUX_RESERVED                             = 20U,
  LMX249x_MUX_OUT_CMP0RAMP                         = 22U,
  LMX249x_MUX_OUT_CMP1RAMP                         = 23U,
  LMX249x_MUX_OUT_FASTLOCK                         = 28U,
  LMX249x_MUX_OUT_CPG_FROM_RAMP                    = 29U,
  LMX249x_MUX_OUT_FLAG0_FROM_RAMP                  = 30U,
  LMX249x_MUX_OUT_FLAG1_FROM_RAMP                  = 31U,
  LMX249x_MUX_OUT_TRIGA                            = 32U,
  LMX249x_MUX_OUT_TRIGB                            = 33U,
  LMX249x_MUX_OUT_TRIGC                            = 34U,
  LMX249x_MUX_OUT_R_DIVIDE                         = 35U,
  LMX249x_MUX_OUT_CPUP                             = 36U,
  LMX249x_MUX_OUT_CPDN                             = 37U,
  LMX249x_MUX_OUT_RAMP_CNT_FINISHED                = 38U
} Lmx249x_MUX_t;
/** @} */

/**
 * \brief LMX249x pin function of PLL input/output.
 * @{
 */
typedef enum
{
  LMX249x_PIN_FCN_TRISTATE                         = 0U,
  LMX249x_PIN_FCN_OPEN_DRAIN_OUT                   = 1U,
  LMX249x_PIN_FCN_PULLUPDN_OUT                     = 2U,
  LMX249x_PIN_FCN_GND                              = 4U,
  LMX249x_PIN_FCN_INVERTED_OPEN_DRAIN_OUT          = 5U,
  LMX249x_PIN_FCN_INVERTED_PULUPDN_OUT             = 6U,
  LMX249x_PIN_FCN_INPUT                            = 7U
} Lmx249x_Pin_Function_t;
/** @} */

/**
 * \brief LMX249x charge pump polarity.
 * @{
 */
typedef enum
{
  LMX249x_CPPOL_NEGATIVE                           = 0U,
  LMX249x_CPPOL_POSITIVE                           = 1U
} Lmx249x_Charge_Pump_Polarity_t;
/** @} */

/**
 * \brief LMX249x digital lock detect tolerance.
 * @{
 */
typedef enum
{
  LMX249x_DLD_TOL_1NS                              = 0U,
  LMX249x_DLD_TOL_1_7NS                            = 1U,
  LMX249x_DLD_TOL_3NS                              = 2U,
  LMX249x_DLD_TOL_6NS                              = 3U,
  LMX249x_DLD_TOL_10NS                             = 4U,
  LMX249x_DLD_TOL_18NS                             = 5U
} Lmx249x_DLD_Tolerance_t;
/** @} */

/**
 * \brief LMX249x power operation status.
 * @{
 */
typedef enum
{
  LMX249x_POWER_DOWN                               = 0U,    /**< Power down, ignore CE */
  LMX249x_POWER_UP                                 = 1U,    /**< Power up, ignore CE */
  LMX249x_POWER_CE                                 = 2U     /**< Power state controlled by CE Pin */
} Lmx249x_Power_State_t;
/** @} */

/**
 * \brief LMX249x Oscillator input frequency.
 * @{
 */
typedef enum
{
  LMX249x_OSCIN_DOUBLER_OFF                        = 0U,    /**< OSCin frequency is used as is */
  LMX249x_OSCIN_DOUBLER_ON                         = 1U     /**< OSCin frequency is doubled */
} Lmx249x_Oscillator_Input_Doubler_t;
/** @} */

/**
 * \brief LMX249x Oscillator input frequency mode.
 * @{
 */
typedef enum
{
  LMX249x_OSCIN_SINGLE_ENDED                       = 0U,    /**< OSCin Pin is connected single ended */
  LMX249x_OSCIN_DIFFERENTIAL                       = 1U     /**< OSCIN Pin is connected to a differential signal */
} Lmx249x_Oscillatior_Input_Mode_t;
/** @} */

/**
 * \brief LMX249x charge pump pulse width.
 * @{
 */
typedef enum
{
  LMX249x_CP_PULSE_860PS                           = 1U,    /**< charge pump pulse width of 860ps (recommended) */
  LMX249x_CP_PULSE_1200PS                          = 2U,    /**< charge pump pulse width of 1200ps */
  LMX249x_CP_PULSE_1500PS                          = 3U     /**< charge pump pulse width of 1500ps */
} Lmx249x_Charge_Pump_Pulse_Width_t;
/** @} */

/**
 * \brief LMX249x Cycle Slip operation.
 * @{
 */
typedef enum
{
  LMX249x_CSR_DISABLED                             = 0U,    /**< Disable Cycle Slip Reduction (recommended when ramp generator is used) */
  LMX249x_CSR_X2                                   = 1U,    /**< Reduce cycle slip by multiplying counters by 2 */
  LMX249x_CSR_X4                                   = 2U     /**< Reduce cycle slip by multiplying counters by 4 */
} Lmx249x_Cycle_Slip_Reduce_t;
/** @} */

/**
 * \brief LMX249x Error code.
 * @{
 */
typedef enum
{
  LMX249x_ERROR_CODE_OK                            = 0U,
  LMX249x_ERROR_CODE_INVALID_NUMBER_OF_RAMPS       = 1U
} Lmx249x_Error_Code_t;
/** @} */

/**
 * \brief LMX249x SPI function pointer, responsible for SPI data transmission via SPI protocol.
 * @{
 */
typedef s32 (*sendSPIFunction)(XSpiPs *SpiInstancePtr, u8 *SendBufPtr,u8 *RecvBufPtr, u32 ByteCount);
/** @} */

/**
 * \brief Contains LMX249x hardware setup parameters and is used by LMX249x_init() function
 * @{
 */
typedef struct
{
  double                              dReferenceFreq;         /**< The frequency of the reference oscillator */
  uint16_t                            uReferenceDivider;      /**< The Reference Frequency is divided by this factor */
  Lmx249x_Oscillator_Input_Doubler_t  eReferenceDoubler;      /**< If this is non zero, the reference frequency is doubled by clocking on falling and rising edge */
  Lmx249x_Oscillatior_Input_Mode_t    eOscInMode;             /**< The way the Oscillator input is connected */
  uint32_t                            uExternalDivider;       /**< An external divide factor inside the loop circuitry (used to translate target frequencies to the frequencies the PLL sees) */
  Lmx249x_MUX_t                       eTrig1PinFunction;      /**< The function routed to the TRIG1 Pin */
  Lmx249x_Pin_Function_t              eTrig1PinDriveMode;     /**< The driver mode for the TRIG1 Pin */
  Lmx249x_MUX_t                       eTrig2PinFunction;      /**< The function routed to the TRIG2 Pin */
  Lmx249x_Pin_Function_t              eTrig2PinDriveMode;     /**< The driver mode for the TRIG2 Pin */
  Lmx249x_MUX_t                       eModPinFunction;        /**< The function routed to the MOD Pin */
  Lmx249x_Pin_Function_t              eModPinDriveMode;       /**< The driver mode for the MOD Pin */
  Lmx249x_MUX_t                       eMUXoutPinFunction;     /**< The function routed to the MUXout Pin */
  Lmx249x_Pin_Function_t              eMUXoutPinDriveMode;    /**< The driver mode for the MUXout Pin */
  Lmx249x_Charge_Pump_Polarity_t      eChargePumpPolarity;    /**< Positive or Negative charge pump gain */
  uint8_t                             uChargePumpCurrent;     /**< The charge pump current in 100uA for normal operation mode */
  uint8_t                             uChargePumpCurrentFS;   /**< The charge pump current in 100uA for fast lock mode */
  uint8_t                             uChargePumpThresholdLo; /**< The lower threshold for lock detection */
  uint8_t                             uChargePumpThresholdHi; /**< The upper threshold for lock detection */
  Lmx249x_Charge_Pump_Pulse_Width_t   eChargePumpPulseWidth;  /**< Charge pump pulse width in ps */
  Lmx249x_Cycle_Slip_Reduce_t         eCycleSlipReduction;    /**< Cycle slip related information */
  uint16_t                            uFastLockTimer;         /**< The fast Lock timer is initialized with this value multiplied by 32 */
  uint8_t                             uLockDetectNumGoodEdge; /**< In a lock detect time window at least this number of good edges must occur, until a lock is detected */
  uint8_t                             uLockDetectNumBadEdge;  /**< In a lock detect time window at most this number of bad edges must occur, until a lock is detected */
  Lmx249x_DLD_Tolerance_t             eLockDetectWindow;      /**< Digital Lock detect edge window */
  XSpiPs*                             SPI_devicePtr;
} Lmx249x_Hardware_Setup_t;
/** @} */

/**
 * \brief Contains Ramp generator parameters that are not specific to a single section.
 * @{
 */
typedef struct
{
  double                            dBaseFrequency;         /**< Signed ramp increment */
  double			    dDeviationFrequency;    /**< Signed deviation frequency for FSK operation */
  double                            dMinFrequency;          /**< Minimum frequency that can't be underrun by a ramp */
  double                            dMaxFrequency;          /**< Maximum frequency that can't be overrun by a ramp */
  double                            dComp0Freq;             /**< Frequency that is used by Comparator 0 to compare the ramp with */
  double                            dComp1Freq;             /**< Frequency that is used by Comparator 0 to compare the ramp with */
  Lmx249x_Ramp_Trigger_Source_t     eTriggerA;              /**< Define the source for Trigger A */
  Lmx249x_Ramp_Trigger_Source_t     eTriggerB;              /**< Define the source for Trigger B */
  Lmx249x_Ramp_Trigger_Source_t     eTriggerC;              /**< Define the source for Trigger C */
  Lmx249x_Ramp_Clock_t              eRampClock;             /**< Determines if internal or external clock for ramp timing is used */
  Lmx249x_Ramp_Modulation_t         eModulation;            /**< Kind of modulation */
  Lmx249x_Ramp_AutoOff_t            eAutoOff;               /**< Defines, if the Ramp should be turned off after a certain amount of ramps */
  uint16_t                          uNumRamps;              /**< Number of ramps to do before ramp is disabled (set to 0 for infinite number of ramps) */
  Lmx249x_Ramp_Trig_Inc_t           eRampCountTrigger;      /**< Defines the increment trigger for the ramp counter */
  Lmx249x_Trigger_Select_t          eDevTrigger;            /**< Defines the FSK deviation trigger */
  Lmx249x_Frac_Order_t              eFracOrder;		    /**< Defines the fractional order */
  Lmx249x_Frac_Dither_t             eDitherMode;            /**< Defines the fractional dithering */
} Lmx249x_Ramp_Global_t;
/** @} */

/**
 * \brief Defines a single ramp section, the PLL can define up to 8 ramp sections.
 * @{
 */
typedef struct
{
  double                            dFreqShift;             /**< Signed ramp increment */
  Lmx249x_Ramp_Fast_Lock_t          eFastlock;              /**< Fast lock enable*/
  double                            dTramp;                 /**< Ramp time in units of microseconds. */
  Lmx249x_Ramp_Flag_t               eFlag;                  /**< General purpose FLAGS sent out of RAMP */
  Lmx249x_Ramp_Reset_t              eReset;                 /**< Forces a clear of the ramp accumulator */
  Lmx249x_Ramp_Next_Trig_t          eNextTrig;              /**< Determines the event to trigger the next ramp */
  uint8_t                           uNext;                  /**< The next RAMP to execute when the length counter times out */
  Lmx249x_Ramp_Comparators_t        eComparators;           /**< Determines which comparators should be used during ramping */
} Lmx249x_Ramp_Section_t;
/** @} */

/**
 * \brief An instance of this structure is passed to every call of LMX249x functions.
 * @{
 */
typedef struct
{
  double                            dExternalDivideFactor;  /**< This factor is applied to all frequencies coming in through
                                                                 the API. This is just for convenience, so the user can work
                                                                 with target frequencies, when the hardware setup has a
                                                                 built-in frequency divider. */
  double                            dPFDCycleTime;          /**< This is the PFD cycle time, given frequencies are scaled
                                                                 with this factor to get a counter value. */
  uint8_t                           uReg58;                 /**< This stores the content of register 58 to enable and disable
                                                                 ramping without reconfiguring the ramps */
  XSpiPs*                           SPI_devicePtr;             /**< This is the SPI device >*/
  sendSPIFunction                   sendSPI;                /**< This function is used to send SPI data */

  void*                             pDataForSendSPI;        /**< This function is passed to the send SPI data function */
} Lmx249x_Object_t;
/** @} */

/*
==============================================================================
   3. FUNCTION PROTOTYPES
==============================================================================
 */

/**
 * \brief This function initializes the LMX249x PLL.
 *
 * \param[in]	*pThis 		 Pointer to LMX249x structure instance
 * \param[in]	*pSetup          Pointer to LMX249x hardware setup structure
 * \param[in]	*sendSPI 	 Pointer to SPI data transmission function
 * \param[in]	*pDataForSendSPI Pointer to SPI digital IO structure
 *
 * \return None
 */
s32 lmx249x_init(Lmx249x_Object_t* pThis, const Lmx249x_Hardware_Setup_t* pSetup,
                  sendSPIFunction sendSPI);

/**
 * \brief This function sets LMX249x power state.
 *
 * \param[in]	*pThis 	Pointer to LMX249x structure instance
 * \param[in]	eState 	LMX249x power state
 *
 * \return None
 */
s32 lmx249x_set_power_state(Lmx249x_Object_t* pThis, Lmx249x_Power_State_t eState);

/**
 * \brief This function sets the frequency for the PLL to oscillate.
 *
 * \param[in]	*pThis 		Pointer to LMX249x structure instance
 * \param[in] 	dBaseFrequency 	Used base frequency
 * \param[in] 	eFracOrder 	Fractional order
 * \param[in] 	eDitherMode 	Pointer to SPI digital IO structure
 *
 * \return One of the following status can be return:
 *   	   - \ref LMX249x_ERROR_CODE_OK    						Success
 *   	   - \ref LMX249x_ERROR_CODE_INVALID_NUMBER_OF_RAMPS	Fail
 */
Lmx249x_Error_Code_t lmx249x_set_frequency(Lmx249x_Object_t* pThis, double dBaseFrequency,
                                         Lmx249x_Frac_Order_t eFracOrder,
                                         Lmx249x_Frac_Dither_t eDitherMode);

/**
 * \brief This function defines up to 8 ramps.
 *
 * \param[in]	*pThis 			Pointer to LMX249x structure instance
 * \param[in] 	*pGlobalSettings 	Pointer to the Ramp parameters structure
 * \param[in] 	*pRampSections 		Pointer to a single ramp section
 * \param[in] 	pRampSectionsIdx	Index of the ramp section
 *
 * \return One of the following status can be return:
 *   	   - \ref LMX249x_ERROR_CODE_OK    						Success
 *   	   - \ref LMX249x_ERROR_CODE_INVALID_NUMBER_OF_RAMPS	Fail
 */
Lmx249x_Error_Code_t lmx249x_configure_ramps(Lmx249x_Object_t* pThis,
                                           const Lmx249x_Ramp_Global_t* pGlobalSettings,
                                           const Lmx249x_Ramp_Section_t* pRampSections,
                                           uint8_t pRampSectionsIdx);

/**
 * \brief This function enables or disables ramp mode of the PLL.
 *
 * \param[in]	*pThis 	Pointer to LMX249x structure instance
 * \param[in]	bEnable	This parameter can be true or false
 *
 * \return None
 */
int lmx249x_enable_ramps(Lmx249x_Object_t* pThis, uint8_t bEnable);

/**
 * \brief This function calculates the fractional accurate bandwidth to avoid overflow of accumulator inside PLL
 *        Without this correction, multiple ramps may have long delays.
 *
 * \param[in]	*pThis 			Pointer to LMX249x structure instance
 * \param[in]	FreqShift_MHz 		Frequency Shift in MHz (Bandwidth in MHz)
 * \param[in] 	FreqShift_time_usec	Chirp time in units of microseconds.
 *
 * \return The real frequency shift based on PLL clock
 */
double lmx249x_get_real_frequency_shift(Lmx249x_Object_t* pThis, double FreqShift_MHz, uint32_t FreqShift_time_usec);

/**
 * \brief  This function sets DIGITAL_IO_PLL_TRIG2 pin to high to trigger the start generation of ramps.
 */
void lmx249x_trigger_ramp(void);

/**
 * \brief  This function sets DIGITAL_IO_PLL_TRIG1 pin to low to bring the trigger to down state.
 */
void lmx249x_release_ramp_trigger(void);

/**
 * \brief  This function sets DIGITAL_IO_PLL_CE pin to high to enable the CE of PLL, used in power-up phase of duty cycle.
 */
void lmx249x_power_up(void);

/**
 * \brief  This function sets DIGITAL_IO_PLL_CE pin to low to disable the CE of PLL, used in power-down phase of duty cycle.
 */
void lmx249x_power_down(void);

/* --- Close open blocks -------------------------------------------------- */

/* Disable C linkage for C++ files */
#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */

#endif /* LMX249X_H_ */

/* --- End of File -------------------------------------------------------- */