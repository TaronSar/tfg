#ifndef BGT24MTR1X_H_
#define BGT24MTR1X_H_

/* Enable C linkage if header is included in C++ files */
#ifdef __cplusplus
extern "C"
{
#endif /* __cplusplus */

#include "../../PS_DRIVERs/SPI/SPI_device.h"
#include "../../PS_DRIVERs/DIGITAL_IO/digital_io.h"
#include "stdbool.h"

#define	BGT24MTR1X_BASE_CONF         (0x1048U)   /**< 0x1048 = 0001 0000  0100 1000 */

/**
 * @brief BGT24MTR1x default power configuration.
 */
#define BGT24MTR1X_POWER_CONF               (0x1047U)   /**< 0x1047 = 0001 0000  0100 0111 */

/**
 * @brief BGT24MTR1x SPI control word settings.
 */
#define BGT24MTR1X_ENA_LNA_MASK             (0x7FFFU)   /**< LNA Gain increase; 0 = increase LNA gain */
#define BGT24MTR1X_DIS_LNA_MASK             (0x8000U)   /**< LNA Gain reduction; 1 = reduce LNA gain */
#define BGT24MTR1X_ENA_PA_MASK              (0xEFFFU)   /**< ENABLE PA - 0 = turn on TX power */
#define BGT24MTR1X_DIS_PA_MASK              (0x1000U)   /**< DISABLE PA - 1 = turn off TX power */
#define BGT24MTR1X_DIS_DIV64K_MASK          (0x0040U)   /**< 1 = Disable 64K divider for Q2 */
#define BGT24MTR1X_DIS_DIV16_MASK           (0x0020U)   /**< 1 = Disable 16 divider for Q2 */
#define BGT24MTR1X_PC2_BUF_MASK             (0x0010U)   /**< PC2_BUF 1 = High LO buffer output power */
#define BGT24MTR1X_PC1_BUF_MASK             (0x0008U)   /**< PC1_BUF 1 = High TX buffer output power */
#define BGT24MTR1X_PC_PA_MASK               (0x0007U)   /**< PC0_PA, PC1_PA, PC2_PA,  1 = reduce TX power */

/**
 * @brief BGT24MTR1x AMUX settings.
 */
#define BGT24MTR1X_AMUX_0                 (0x0080U)   /**< BGT AUMUX_0 Mask */
#define BGT24MTR1X_AMUX_1                 (0x0100U)   /**< BGT AUMUX_1 Mask */
#define BGT24MTR1X_AMUX_2                 (0x2000U)   /**< BGT AUMUX_2 Mask */
#define BGT24MTR1X_AMUX_VOUT_TX           (0xDE7FU)   /**< BGT AUMUX_VOUT Mask */


/**
 * @brief BGT24MTR1x index of the ANA output Command from AMUX pin.
 */
#define BGT24MTR1X_ANA_CMD_TEMPERATURE      (0x0U)   /**< Command to read the temperature output from AMUX pin */
#define BGT24MTR1X_ANA_CMD_TX_POWER         (0x1U)   /**< Command to read the output TX power from AMUX pin */
#define BGT24MTR1X_ANA_CMD_TX_POWER_REF     (0x2U)   /**< Command to read the reference TX power from AMUX pin */

/**
 * @brief BGT24MTR1x TX PA settings.
 */
#define	BGT24MTR1X_PC_PA_0                  (0x0000U)   /**< Max Tx power, no reduction */
#define	BGT24MTR1X_PC_PA_1                  (0x0001U)   /**< Max Tx power, no reduction */
#define	BGT24MTR1X_PC_PA_2                  (0x0002U)   /**< Reduction by 0.8dBm */
#define	BGT24MTR1X_PC_PA_3                  (0x0003U)   /**< Reduction by 1.4dBm */
#define	BGT24MTR1X_PC_PA_4                  (0x0004U)   /**< Reduction by 2.5dBm */
#define	BGT24MTR1X_PC_PA_5                  (0x0005U)   /**< Reduction by 4dBm */
#define	BGT24MTR1X_PC_PA_6                  (0x0006U)   /**< Reduction by 6dBm */
#define	BGT24MTR1X_PC_PA_7                  (0x0007U)   /**< Reduction by 9dBm */

/**
 * @brief BGT24MTR1x Number of Tx and Rx Antennas.
 */
#define BGT24MTR1X_NUM_TX_ANTENNAS          (1U)   		/**< TX antennas in BGT24MTR1x */
#define BGT24MTR1X_NUM_RX_ANTENNAS          (2U)   		/**< RX antennas in BGT24MTR12 */

/**
 * @brief BGT24MTR1x Number of temperature sensors.
 */
#define BGT24MTR1X_NUM_TEMP_SENSORS         (uint8_t)1U   /**< Number of temperature sensor in BGT24MTR12 */

/**
 * @brief BGT24MTR1x Max Tx Power Level.
 */
#define BGT24MTR1X_MAX_TX_POWER_LEVEL       (7U)   /**< Maximum BGT TX output power SPI input value range is [0 - 7] */

/**
 * @brief BGT24MTR1x Min and Max RF supported frequencies.
 */
#define BGT24MTR1X_MIN_RF_FREQUENCY_KHZ     (24025000U)   /**< Minimum RF frequency supported by BGT24MTR1x in kHz */
#define BGT24MTR1X_MAX_RF_FREQUENCY_KHZ     (24225000U)   /**< Maximum RF frequency supported by BGT24MTR1x in kHz */

/*
==============================================================================
   3. TYPES
==============================================================================
 */

/**
 * \brief Defines LNA gain Enable/disable state.
 * @{
 */
typedef enum
{
  BGT24MTR1X_LNA_DISABLE       = 0U,   /**< LNA gain disabled */
  BGT24MTR1X_LNA_ENABLE        = 1U    /**< LNA gain enabled */
} Bgt24mtr1x_LNAgain_t;
/** @} */

/**
 * \brief Defines possible power levels of BGT Tx power amplifier. Use type Bgt24mtr1x_Power_t for this enum.
 * @{
 */
typedef enum
{
  BGT24MTR1X_TX_MIN            = 0U,   /**< Reduction by 9dBm */
  BGT24MTR1X_TX_LEVEL_1        = 1U,   /**< Reduction by 6dBm */
  BGT24MTR1X_TX_LEVEL_2        = 2U,   /**< Reduction by 4dBm */
  BGT24MTR1X_TX_MID            = 3U,   /**< Reduction by 2.5dBm */
  BGT24MTR1X_TX_LEVEL_4        = 4U,   /**< Reduction by 1.4dBm */
  BGT24MTR1X_TX_LEVEL_5        = 5U,   /**< Reduction by 0.8dBm */
  BGT24MTR1X_TX_LEVEL_6        = 6U,   /**< Reduction by 0.4dBm */
  BGT24MTR1X_TX_MAX            = 7U    /**< No Reduction, Max Tx Power */
} Bgt24mtr1x_Power_t;
/** @} */

/**
 * \brief LMX249x SPI function pointer, responsible for SPI data transmission via SPI protocol.
 * @{
 */
typedef s32 (*sendSPIFunction)(XSpiPs *SpiInstancePtr, u8 *SendBufPtr,u8 *RecvBufPtr, u32 ByteCount);
/** @} */

/**
 * \brief An instance of BGT structure
 * @{
 */
typedef struct
{
	Bgt24mtr1x_LNAgain_t 		LNAgain;
	Bgt24mtr1x_Power_t	    Power_Tx;
	XSpiPs*					     SPI_Ptr_bgt;
	sendSPIFunction         sendSPI;
} BGT_Object;

/*
==============================================================================
   4. FUNCTION PROTOTYPES
==============================================================================
 */

/**
* \brief  This function initializes the BGT24MTR1x 16-bit SPI shadow register and send BGT settings.
 *        RX LNA enable or disable settings and TX out put power level are also set in this function.
 *
 * \param[in]  lna_gain     Enable or disable LNA gain, these values are matched to the Power levels defined by enum \ref BGT24MTR1x_LNAGain_t
 * \param[in]  power_level  TX power level, these values are matched to the Power levels defined by enum \ref BGT24MTR1x_LNAGain_t
 *
 * \return None
 *
 * Bit description of 16-bit SPI shadow register in BGT is explained below;
 *  - 15      GS LNA Gain reduction (low)
 *  - 14      Not used (low)
 *  - 13      Not used (low)
 *  - 12      DIS_PA TX power disabled (high)
 *  - 11      AMUX2 Analog multiplexer control bit 2 (high)
 *  - 10      Test bit, must be low otherwise malfunction (low)
 *  - 9       Test bit, must be low otherwise malfunction (low)
 *  - 8       AMUX1 Analog multiplexer control bit 1 (low)
 *  - 7       AMUX0 Analog multiplexer control bit 0 (low)
 *  - 6       DIS_DIV64k Disable 64k divider Q2 (low)
 *  - 5       DIS_DIV16 Disable 16 divider Q1 (low)
 *  - 4       PC2_BUF High LO buffer output power in ?high? mode otherwise typ. 4dB reduced LO-output power (low)
 *  - 3       PC1_BUF High TX buffer output power (low)
 *  - 2       PC2_PA TX power reduction bit 2 (high)
 *  - 1       PC1_PA TX power reduction bit 1 (high)
 *  - 0       PC0_PA TX power reduction bit 0 (high)
 */

void bgt24mtr1x_init( Bgt24mtr1x_LNAgain_t lna_gain, Bgt24mtr1x_Power_t power_level);

/**
 * \brief 	This function enables BGT24MTR1x TX Power amplifier to start transmission.
 *		    12th bit of SPI shadow register in BGT24MTR1x is enabled (high).
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_start_tx(BGT_Object* txrx_handle);

/**
 * \brief 	This function disables BGT24MTR1x TX Power amplifier.
 *		    12th bit of SPI shadow register in BGT24MTR1x is disabled (low).
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_stop_tx(BGT_Object* txrx_handle);

/**
 * \brief 	This function enables the GPIO to connect the switch between BGT24MTR1x and VCC.
 *
 * \Note	This function is used in duty cycle mode. Before data acquisition this should be enabled with at least 1ms of delay for settling up BGT.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_power_up(void);

/**
 * \brief 	This function disables the GPIO to disconnect the switch between BGT24MTR1x and VCC.
 *
 * \Note	This function is used in duty cycle mode. After data acquisition this should be disabled.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_power_down(void);

/**
 * \brief 	This function sets the power level [0- 7] of BGT24MTR1x TXP Power amplifier.
 *
 * \Note	Setting TX power level will make sense only if 12th-bit of BGT24MTR1x SPI register is enabled.
 *
 * \param[in]  power_level  Unsigned 8-bit integer, whose values are matched to the Power levels defined by enum \ref Bgt24mtr1x_Power_t.
 *
 * \return None
 */
void bgt24mtr1x_set_tx_power(Bgt24mtr1x_Power_t power_level);

/**
 * \brief 	This function is used to get the power level [0 - 7] of BGT24MTR1x TX Power amplifier.
 *
 * \param[in]  None
 *
 * \return  Unsigned 8-bit integer, whose values are matched to the Power levels defined by enum \ref Bgt24mtr1x_Power_t.
 */
uint8_t bgt24mtr1x_get_tx_power(void);

/**
 * \brief 	This function enables the Receiver LNA gain, which gives almost 6dB gain increase.
 *
 * \Note    By default this LNA gain is enabled/disabled based on config.h in the BGT24MTR1x_init() function.
 * 			Changing this setting requires to do the calibration again.
 *			15th-bit: Set this bit to low to disable the LNA Gain reduction which means enabling the 6dB LNA gain.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_lna_gain_enable(void);

/**
* \brief   This function disables the Receiver LNA gain.
 *
 * \Note   By default this LNA gain is enabled/disabled based on config.h in the BGT24MTR1x_init() function.
 *         Changing this setting requires to do the calibration again.
 *         15th-bit: Set this bit to low to disable the LNA Gain reduction which means enabling the 6dB LNA gain.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_lna_gain_disable(void);

/**
 * \brief This function returns the current status of the Receiver LNA gain, if enabled it returns true else false.
 *
 * \param[in]  None
 *
 * \return	Unsigned 8-bit integer, 0 for false and non-zero for true case.
 */
uint8_t bgt24mtr1x_lna_gain_is_enable(void);

/**
 * \brief This function transmits the 16-bit SPI settings to BGT24MTR1x registers \ref bgt24mtr1x_global_config.
 *
 * \param[in]  config_val  Unsigned 16-bit containing current SPI settings for BGT24MTR1x.
 *
 * \return None
 */
void bgt24mtr1x_set_config(XSpiPs *SpiInstancePtr, uint16_t config_val);

/**
 * \brief This function returns the 16-bit SPI settings for BGT24MTR1x defined by the shadow register \ref bgt24mtr1x_global_config.
 *
 * \param[in]  None
 *
 * \return	Unsigned 16-bit integers containing current settings for BGT24MTR1x
 */
uint16_t bgt24mtr1x_get_config(void);

/**
 * \brief This function sets the SPI settings for BGT24MTR1x to read the temperature output from AMUX pin.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_ana_temp(void);

/**
 * \brief This function sets the SPI settings for BGT24MTR1x to read the output TX power from AMUX pin.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_ana_vout_tx(void);

/**
 * \brief This function sets the SPI settings for BGT24MTR1x to read the reference TX power from AMUX pin.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_ana_vref_tx(void);

/**
 * \brief This function returns the current settings for Analog output defined by \ref BGT24MTR1x_AnaCommand.
 *
 * \return	Unsigned 16-bit integers containing current settings for Analog output
 */
uint16_t bgt24mtr1x_get_ana_config(void);

/**
 * \brief This function sets the lowest power with q2 disable for BGT24MTR1x.
 *
 * \param[in]  None
 *
 * \return None
 */
void bgt24mtr1x_lowest_power_with_q2_disable(void);



/* Disable C linkage for C++ files */
#ifdef __cplusplus
} /* extern "C" */
#endif /* __cplusplus */

#endif /* BGT24MTR1X_H_ */

/* --- End of File -------------------------------------------------------- */
