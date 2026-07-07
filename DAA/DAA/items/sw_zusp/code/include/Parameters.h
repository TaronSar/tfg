#ifndef ZUSP_PARAMS_H_
#define ZUSP_PARAMS_H_

#include <Entypes.h>
#include <hw_types.h>

/// General constants
const Uint8 master_core_id = 0;
const Uint8 max_n_cores = 4;
const Uint8 init_core_irq = 15;
const Uint32 register_bytes = 4;

// Exceptions
const Uint32 exc_id_sync_int = 1U;      /// Exception id Syncronous interruption
const Uint32 exc_id_irq_int  = 2U;      /// Exception id IRQ interruption
const Uint32 exc_id_fiq_int  = 3U;      /// Exception id FIQ interruption
const Uint32 exc_id_sea_int  = 4U;      /// Exception id system error abort interruption
const Uint32 exc_id_last     = 5U;      /// Exception id last interruption


//  UART offsets
const Uint32 UARTPS_cr_offs = 0x0000U;              /// *< Control Register [8:0] */
const Uint32 UARTPS_mr_offs = 0x0004U;  		    /// *< Mode Register [9:0] */
const Uint32 UARTPS_ier_offs = 0x0008U;             /// *< Interrupt Enable [12:0] */
const Uint32 UARTPS_idr_offs = 0x000CU;             /// *< Interrupt Disable [12:0] */
const Uint32 UARTPS_int_offs = 0x00000010U;         /// *< Interrupt Offset */
const Uint32 UARTPS_isr_offs = 0x0014U;             /// *< Interrupt Status [12:0]*/
const Uint32 UARTPS_rxo_offs = 0x001CU;             /// *< RX Timeout [7:0] */
const Uint32 UARTPS_bdg_offs = 0x0018U;             /// *< Baud Rate Generator [15:0] */
const Uint32 UARTPS_rxw_offs = 0x0020U;             /// *< RX FIFO Trigger Level [5:0] */
const Uint32 UARTPS_sr_offs = 0x002CU;              /// *< Channel Status [14:0] */
const Uint32 UARTPS_ffo_offs = 0x0030U;             /// *< FIFO [7:0] */
const Uint32 UARTPS_bdd_offs = 0x0034U;             /// *< Baud Rate Divider [7:0] */
const Uint32 UARTPS_txw_offs = 0x0044U;             /// *< TX FIFO Trigger Level [5:0] */

//  UART masks
const Uint32 UARTPS_chl_mask = 0x00000006U;         /// *< Data length mask */
const Uint32 UARTPS_par_mask = 0x00000038U;         /// *< Parity mask */
const Uint32 UARTPS_end_mask = 0x0000003CU;  	    /// *< Enable/disable Mask */
const Uint32 UARTPS_stp_mask = 0x000000A0U;         /// *< Stop bits mask */
const Uint32 UARTPS_ixr_mask = 0x00001FFFU;         /// *< Valid bit mask */
const Uint32 UARTPS_ffo_mask = 0x3000U;             /// *< Reset TX FIFO size access */

//  UART registers
const Uint32 UARTPS_ffo_B = 0x1000U;                    /// *< Value of sent bytes (TX FIFO) */
const Uint32 UARTPS_txrst = 0x00000002U;                /// *< TX logic reset */
const Uint32 UARTPS_rxrst = 0x00000001U;                /// *< RX logic reset */
const Uint32 UARTPS_ch_norm = 0x00000000U;              /// *< Normal mode */
const Uint32 UARTPS_rxw_rst = 0x00000020U;              /// *< Reset value */
const Uint32 UARTPS_txw_rst = 0x00000020U;              /// *< Reset value */
const Uint32 UARTPS_rxo_dis = 0x00000000U;              /// *< Disable time out */
const Uint32 UARTPS_bdg_rst = 0x0000028BU;              /// *< Reset value */
const Uint32 UARTPS_bdd_rst = 0x0000000FU;              /// *< Reset value */
const Uint32 UARTPS_rx_dis = 0x00000008U;               /// *< RX disabled. */
const Uint32 UARTPS_tx_dis = 0x00000020U;               /// *< TX disabled. */
const Uint32 UARTPS_stopbrk = 0x00000100U;              /// *< Stop transmission of break */
const Uint32 UARTPS_startbrk = 0x00000080U;             /// *< Start break transmission */
const Uint32 UARTPS_sr_txf = 0x00000010U;               /// *< TX FIFO full */
const Uint32 UARTPS_int_txf = 0x00000100U;              /// *< TX FIFO full (interrupt - send data) */
const Uint32 UARTPS_sr_tx_nf = 0x00004000U;             /// *< TX FIFO nearly full */
const Uint32 UARTPS_sr_txe = 0x00000080U; 	            /// *< TX FIFO empty */
const Uint32 UARTPS_int_txe = 0x00000008U; 	            /// *< TX FIFO empty (interrupt - send data) */
const Uint32 UARTPS_sr_rxf = 0x00000004U;               /// *< RX FIFO full interrupt. */
const Uint32 UARTPS_sr_rxe = 0x00000002U;               /// *< RX FIFO empty interrupt. */
const Uint32 UARTPS_sr_rxovr = 0x00000001U;             /// *< RX FIFO trigger interrupt. */
const Uint32 UARTPS_sr_tact = 0x00000800U; 	            /// *< TX active */
const Uint32 UARTPS_clksel = 0x00000001U; 	            /// *< Input clock selection */
const Uint32 UARTPS_tx_en = 0x00000010U;  	            /// *< TX enabled */
const Uint32 rxfifo_data_B = 0x08U;                     /// *< Number of data bytes for trigger - RX FIFO */
const Uint32 rxfifo_tout_dft = 0x01U;                   /// *< Default timeout for RX FIFO */

/// Definitions for driver UART
const Uint32 UART_num_inst = 1U; 

///	UART Driver definitions
const Uint32 UART_0_baseaddr = 0xFF000000;
const Uint32 UART_0_highaddr = 0xFF00FFFF;
const Uint32 UART_1_baseaddr = 0xFF010000;
const Uint32 UART_1_highaddr = 0xFF01FFFF;
const Uint32 UART_clk_hz = 100000000;
const Uint32 UART_ref_ctrl = (0xFF5E0000);
const Uint32 min_clk_div = 8;

/// UART Baud Rate constants
const Uint32 UARTPS_max_rt = 6240000U;
const Uint32 UARTPS_min_rt = 110U;
const Uint32 UARTPS_bde_rt = 3U;                            ///  max % error allowed */
const Uint32 UARTPS_chl_8 = 0x00000000U;                    /// *< 8 bits data */
const Uint32 UARTPS_stp_1 = 0x00000000U;                    /// *< 1 stop bit */
const Uint32 UARTPS_p_none = 0x00000020U;                   /// *< No parity mode */
const Uint32 bst_error = 0xFFFFFFFFU;                       /// *< Best error for UART */
const Uint32 base_10 = 10;
const Uint32 baud_div_max = 255;
const Uint32 baud_div_min = 4;
const int32 max_size_buf = 64;
const int32 min_size_buf = 16;
const int32 mid_size_buf = 32;
const int32 circ_buf_len = 256;
const long min_number = 10L;
const int8 r_char = ((int8)0x0D);
const int8 nl_char = ((int8)0x0A);
const int8 bs_char = ((int8)0x08);
const int8 bel_char = ((int8)0x07);

const Real percent = 100.0f;
const Real rate_precision = 0.5f;
const Real dft_ratio = 16.0f;
const Real max_bits = 64.0f;


///  ****************************************************************

///  AXI-GPIO constants
const Uint32 AXI_GPIO0_offs = 0x0000U;
const Uint32 AXI_GPIO1_offs = 0x0008U;
const Uint32 max_pin_range = 32;
const Uint32 min_pin_range = 0;


///  ****************************************************************

///  DMA constants
const Uint32 DMA_m2s_cr_offs  = 0x00U;
const Uint32 DMA_m2s_sr_offs  = 0x04U;
const Uint32 DMA_m2s_SA_offs = 0x18U;               /// SA offset
const Uint32 DMA_m2s_SM_offs = 0x1CU;               /// SA MSB offset
const Uint32 DMA_m2s_l_offs = 0x28U;
const Uint32 DMA_s2m_cr_offs  = 0x30U;
const Uint32 DMA_s2m_sr_offs  = 0x34U;
const Uint32 DMA_s2m_DA_offs     = 0x48U;           /// DA offset
const Uint32 DMA_s2m_DM_offs = 0x4CU;               /// DA MSB offset
const Uint32 DMA_s2m_l_offs = 0x58U;
const Uint32 DMA_ch_offs     = 0x30U;
const Uint32 DMA_cr_rs         = 0x1U;
const Uint32 DMA_cr_reset      = 0x4U;
const Uint32 DMA_sr_idle       = 0x0002U;
const Uint32 DMA_sr_halt       = 0x0001U;
const Uint64 DMA_sr_value       = 0xFFFFFFFFU;
const Uint32 DMA_wait_tries       = 0x0U;           ///  Infinite
const Uint32 rst_time           = 50000;

const Uint32 DMA_adq_addr = 0x80010000U;
const Uint32 DMA_conf_addr = 0xA0000000U;
const Uint32 DMA_data_addr = 0xA0010000U;
const Uint32 DMA_adq_size = 0x40U;
const Uint32 DMA_conf_size = 0x40U;
const Uint32 DMA_ds_s2m = 0x01000000U;              /// Data size


///  ****************************************************************

///  GPIO address
const Uint32 GPIO_baseaddr = 0xFF0A0000U;

///  GPIO LSW (Least Significant Word) output masks
const Uint32 GPIO_data0_LSW = 0x00000000U;
const Uint32 GPIO_data1_LSW = 0x00000008U;
const Uint32 GPIO_data2_LSW = 0x00000010U;
const Uint32 GPIO_data3_LSW = 0x00000018U;
const Uint32 GPIO_data4_LSW = 0x00000020U;
const Uint32 GPIO_data5_LSW = 0x00000028U;

///  GPIO MSW (Most Significant Word) output masks
const Uint32 GPIO_data0_MSW = 0x00000004U;
const Uint32 GPIO_data1_MSW = 0x0000000CU;
const Uint32 GPIO_data2_MSW = 0x00000014U;
const Uint32 GPIO_data3_MSW = 0x0000001CU;
const Uint32 GPIO_data4_MSW = 0x00000024U;
const Uint32 GPIO_data5_MSW = 0x0000002CU;

///  GPIO input data offsets
const Uint32 GPIO_d0_ro_offs = 0x00000060U;
const Uint32 GPIO_d1_ro_offs = 0x00000064U;
const Uint32 GPIO_d2_ro_offs = 0x00000068U;
const Uint32 GPIO_d3_ro_offs = 0x0000006CU;
const Uint32 GPIO_d4_ro_offs = 0x00000070U;
const Uint32 GPIO_d5_ro_offs = 0x00000074U;

///  GPIO direction mode (DIRM) offsets
///  MIO: 0-2    ||    EMIO: 3-5
const Uint32 GPIO_dirm0_offs = 0x00000204U;
const Uint32 GPIO_dirm1_offs = 0x00000244U;
const Uint32 GPIO_dirm2_offs = 0x00000284U;
const Uint32 GPIO_dirm3_offs = 0x000002C4U;
const Uint32 GPIO_dirm4_offs = 0x00000304U;
const Uint32 GPIO_dirm5_offs = 0x00000344U;

///  GPIO output enable (OEN) offsets
const Uint32 GPIO_oen0_offs = 0x00000208U;
const Uint32 GPIO_oen1_offs = 0x00000248U;
const Uint32 GPIO_oen2_offs = 0x00000288U;
const Uint32 GPIO_oen3_offs = 0x000002C8U;
const Uint32 GPIO_oen4_offs = 0x00000308U;
const Uint32 GPIO_oen5_offs = 0x00000348U;

///  GPIO interrupt disable registers
const Uint32 GPIO_int_dis0 = 0x00000214U;
const Uint32 GPIO_int_dis1 = 0x00000254U;
const Uint32 GPIO_int_dis2 = 0x00000294U;
const Uint32 GPIO_int_dis3 = 0x000002D4U;
const Uint32 GPIO_int_dis4 = 0x00000314U;
const Uint32 GPIO_int_dis5 = 0x00000354U;
const Uint32 GPIO_isr_dis = 0xFFFFFFFFU;

///  GPIO bit values
const Uint8 GPIO_min_bits = 26;
const Uint8 GPIO_max_bits = 32;
const Uint8 GPIO_bits_low = 16;


///  ****************************************************************

///  I2C base addresses
const Uint32 I2C0_baseaddr = 0xFF020000U;
const Uint32 I2C1_baseaddr = 0xFF030000U;

///  I2C registers offsets
const Uint32 I2C_cr_offs = 0x00000000U;
const Uint32 I2C_sr_offs = 0x00000004U;
const Uint32 I2C_addr_offs = 0x00000008U;
const Uint32 I2C_data_offs = 0x0000000CU;
const Uint32 I2C_isr_offs = 0x00000010U;
const Uint32 I2C_tr_offs = 0x00000014U;
const Uint32 I2C_slv_ps_offs = 0x00000018U;
const Uint32 I2C_tout_offs = 0x0000001CU;
const Uint32 I2C_isr_en_offs = 0x00000024U;
const Uint32 I2C_isr_ds_offs = 0x00000028U;
const Uint32 I2C_glitch_offs = 0x0000002CU;

///  I2C masks
const Uint32 I2C_isr_mask = 0x00000020U;
const Uint32 I2C_hwc_mask = 0x0000005AU;
const Uint32 I2C_div_A_mask = 0x0000C000U;
const Uint32 I2C_div_B_mask = 0x00003F00U;
const Uint32 I2C_slv_d_mask = 0x00000002U;
const Uint32 I2C_slv_c_mask = 0x00000001U;
const Uint32 I2C_RXRW_mask = 0x00000008U;

///  I2C register values
const Uint32 I2C_isr_dis = 0x000002FFU;
const Uint32 I2C_rst_conf = 0x00000040U;
const Uint32 I2C_tout_rst = 0x000000FFU;
const Uint8 I2C_bus_pin = 8U;
const Uint8 I2C_ctrl_hold = 4U;
const Uint32 I2C_hold_bit = 0x00000010U;
const Uint32 I2C_nea_bit = 0x00000004U;
const Uint32 I2C_set_master = 0x0000005EU;
const Uint32 I2C_rw_master = 0x00000001U;
const Uint32 I2C_slv_m_en = 0x00000066U;
const Uint32 I2C_slv_m_dis = 0x00000020U;
const Uint32 I2C_slv_m_idr = 0x00000010U;
const Uint32 I2C_slv_m_init = 0x0000000FU;
const Uint32 I2C_mst_sd_idr = 0x00000205U;
const Uint32 I2C_slv_sd_idr = 0x0000004FU;
const Uint32 I2C_slv_rcv_idr = 0x000000AFU;
const Uint32 I2C_sr_RXDV = 0x00000020U;
const Uint32 I2C_sr_TXDV = 0x00000040U;
const Uint32 I2C_sr_RXOVF = 0x00000080U;
const Uint32 I2C_slv_clr = 0x0000002CU;
const Uint32 I2C_div_A_shift = 14U;
const Uint32 I2C_div_B_shift = 8U;
const Uint32 I2C_CLK_divisor = 22U;
const Uint32 I2C_div_B_limit = 64U;
const Uint32 I2C_div_A_limit = 3U;
const Uint32 I2C_FIFO_size = 16U;
const Uint32 I2C_CLK_max_400 = 384600U;
const Uint32 I2C_CLK_max_100 = 100000U;
const Uint32 I2C_CLK_min_100 = 90000U;
const Uint8 I2C_max_tr_size = 0xFCU;
const Uint32 I2C_timeout_val = 1000U;           /// Timeout in us

///  32bit register masks
const Uint32 bits16_mask = 0xFFFF0000U;
const Uint32 bits10_mask = 0xFFFFFC00U;
const Uint32 bits8_mask = 0xFFFFFF00U;
const Uint32 inv_bits8_mask = 0x000000FFU;
const Uint32 inv_bits10_mask = 0x000003FFU;
const Uint32 inv_bits32_mask = 0x0000FFFFU;
const Uint32 up_16bits_mask = 0xFF00U;


///  ****************************************************************

/// GIC constants
const Uint32 GIC_base_addr          = 0x00F9000000;
const Uint8  GIC_n_irqs             = 192;              /// Read from Typer register - Interrupt Controller Type Register,
                                                        /// GICD_TYPER - GICv2 architecture specification, p.89
const Uint8  GIC_min_prior          = 255;
const Uint8  GIC_max_prior          = 0;
const Uint32 GICD_icfg_n_int        = 16;
const Uint32 GICD_icfg_int_b        = 2;
const Uint32 GIC_n_sgi              = 16;
const Uint32 GIC_clr_reg            = 0xFFFFFFFF;
const Uint8  GIC_clr_byte           = 0xFF;
const Uint32 GICC_bpr_secure        = 0x2;
const Uint32 GICC_bpr_nsecure       = 0x3;
const Uint8  GIC_def_prior          = 0xA0;
const Uint32 GIC_sgi_idx            = 0; 
const Uint32 GIC_ppi_idx            = 16;
const Uint32 GIC_spi_idx            = 32;

/// GICD 
const Uint32 GICD_reg_size = 32; 

/// GICD offsets
const Uint32 GICD_offs        = 0x10000;
const Uint32 GICD_ctrl_offs   = 0x00;
const Uint32 GICD_typer_offs  = 0x04;
const Uint32 GICD_igrpn_offs  = 0x80;
const Uint32 GICD_isen_offs   = 0x100;
const Uint32 GICD_icen_offs   = 0x180;
const Uint32 GICD_ispen_offs  = 0x200;
const Uint32 GICD_icpen_offs  = 0x280;
const Uint32 GICD_isact_offs  = 0x300;
const Uint32 GICD_icact_offs  = 0x380;
const Uint32 GICD_iprio_offs  = 0x400;
const Uint32 GICD_itarg_offs  = 0x800;
const Uint32 GICD_icfg_offs  = 0xC00;

const Uint32 GICD_sgi_offs      = 0xF00;
const Uint32 GICD_sgi_c_offs    = 0xF10;
const Uint32 GICD_sgi_s_offs    = 0xF20;

/// GICD Masks
const Uint32 GICD_ctlr_grp0     = 0x01;
const Uint32 GICD_ctlr_grp1     = 0x02;
const Uint32 GICD_typer_n_it    = 0x1F;
const Uint32 GICD_sgi_nsatt     = 0x8000;
const Uint32 GICD_sgi_list      = 0x0000000;
const Uint32 GICD_sgi_all       = 0x1000000;
const Uint32 GICD_sgi_self      = 0x2000000;

/// GICC offsets
const Uint32 GICC_offs        = 0x20000;
const Uint32 GICC_ctlr_offs   = 0x00;
const Uint32 GICC_pmr_offs    = 0x04;
const Uint32 GICC_bpr_offs    = 0x08;
const Uint32 GICC_iar_offs    = 0x0C;
const Uint32 GICC_eoir_offs   = 0x10;

/// GICC Masks
const Uint32 GICC_iar_irq_id = 0x000003FF; 


///  ****************************************************************


///  IMX296 devices
const Uint32 I2C_device_num = 0U;           ///  ----> i2c-0 is attached to channel 0
const Uint32 IMX296LQ_id = 0x4AU;           ///  IMX296_SENSOR_INFO_IMX296LQ
                                            ///  https://github.com/raspberrypi/linux/blob/rpi-6.1.y/drivers/media/i2c/imx296.c#L1038
const Uint32 IMX296_b_phase = 0U;           ///  IMX296LQR-C Dataseet p.22 coded according Xilinx IP Demosaic

///  IMX219 defined addresses
const Uint32 I2C_device_addr = 0x1AU;
const Uint32 IMX296_i_addr = 0x3149U;
const Uint32 IMX296_FD0_addr = 0x3300U;
const Uint32 IMX296_a3W_addr= 0x4182U;        
const Uint32 IMX296_PH1_addr = 0x3310U;
const Uint32 IMX296_PV1_addr = 0x3312U;
const Uint32 IMX296_WH1_addr = 0x3314U;
const Uint32 IMX296_WV1_addr = 0x3316U;
const Uint32 IMX296_hm_addr = 0x3014U;
const Uint32 IMX296_vm_addr = 0x3010U;
const Uint32 IMX296_is_addr = 0x3089U;
const Uint32 IMX296_GT_addr = 0x4114U;
const Uint32 IMX296_418_addr = 0x418CU;
const Uint32 IMX296_gd_addr = 0x3212U;
const Uint32 IMX296_BLK_addr = 0x3254U;
const Uint32 IMX296_00_addr = 0x3000U;
const Uint32 IMX296_0A_addr = 0x300AU;
const Uint32 IMX296_0B_addr = 0x300BU;
const Uint32 IMX296_0D_addr = 0x300DU;
const Uint32 IMX296_TRG_addr = 0x30AEU;

/// IMX296 auxiliar registers
const Uint32 IMX296_shs_0 = 0x308DU;
const Uint32 IMX296_shs_1 = 0x308EU;   
const Uint32 IMX296_shs_2 = 0x308FU;   
const Uint32 IMX296_max_shs = 1117U;
const Uint32 IMX296_max_h = 1088U;
const Uint32 IMX296_max_w  = 1456U;

/// Setup constants
const Uint32 IMX296_img_c1 = 30U;
const Uint32 IMX296_img_c2 = 29U;
const Uint32 IMG296_delay1 = 5000U;
const Uint32 IMG296_delay2 = 28000U;
const Uint16 IMX296_half_wd = 1100U;
const Uint16 IMX296_hw_offs = 30U;

const Uint32 IMX296_mask = 0xFFU;
const Uint32 value_8b = 8U;
const Uint32 value_16b = 16U;


///  ****************************************************************


/// Gamma LUT addresses
const Uint32 GLUT_AP_addr = 0x0U;
const Uint32 GLUT_dw_addr = 0x10U;
const Uint32 GLUT_dh_addr = 0x18U;
const Uint32 GLUT_dv_addr = 0x20U;
const Uint32 GLUT0_baseaddr = 0x0800U;
const Uint32 GLUT0_highaddr = 0x0FFFU;
const Uint32 GLUT1_baseaddr = 0x1000U;
const Uint32 GLUT1_highaddr = 0x17FFU;
const Uint32 GLUT2_baseaddr = 0x1800U;
const Uint32 GLUT2_highaddr = 0x1FFFU;
const Uint32 GLUT0_A_b_addr = 0xB0050000U;

/// Auxiliar Gamma LUT variables
const Uint32 GLUT_st_val = 0x80U;


///  ****************************************************************


/// Demosaic base addresses
const Uint32 Dem0_baseaddr = 0xB0040000U;

/// Demosaic addresses
const Uint32 Dem_ap_addr = 0x00U;
const Uint32 Dem_dw_addr = 0x10U;
const Uint32 Dem_dh_addr = 0x18U;
const Uint32 Dem_bd_addr = 0x28U;

/// Auxiliar Demosaic variables
const Uint32 Dem_start_data = 0x80U;


///  ****************************************************************


///  V_proc_SS offsets
const Uint32 VPSS_ctrl_offs = 0x00U;
const Uint32 VPSS_in_offs = 0x10U;
const Uint32 VPSS_out_offs = 0x18U;
const Uint32 VPSS_w_offs = 0x20U;
const Uint32 VPSS_h_offs = 0x28U;
const Uint32 VPSS_K11_offs = 0x50U;
const Uint32 VPSS_K12_offs = 0x58U;
const Uint32 VPSS_K13_offs = 0x60U;
const Uint32 VPSS_K21_offs = 0x68U;
const Uint32 VPSS_K22_offs = 0x70U;
const Uint32 VPSS_K23_offs = 0x78U;
const Uint32 VPSS_K31_offs = 0x80U;
const Uint32 VPSS_K32_offs = 0x88U;
const Uint32 VPSS_K33_offs = 0x90U;
const Uint32 VPSS_R_offs = 0x98U;
const Uint32 VPSS_G_offs = 0xA0U;
const Uint32 VPSS_B_offs = 0xA8U;
const Uint32 VPSS_clamp_offs = 0xB0U;
const Uint32 VPSS_clip_offs = 0xB8U;

///  V_proc_SS bits
const Uint8 VPSS_st_bit = 0x01U;
const Uint8 VPSS_dn_bit = 0x02U;
const Uint8 VPSS_id_bit = 0x04U;
const Uint8 VPSS_rd_bit = 0x08U;
const Uint8 VPSS_rst_bit = 0x80U;

///  V_Proc_SS registers
const Uint32 VPSS_scale_coef = 4096U;
const Real VPSS_K11_factor = 0.299f;
const Real VPSS_K12_factor = 0.587f;
const Real VPSS_K13_factor = 0.114f;
const Uint32 VPSS_base_addr = 0xB0000000U;


///  ****************************************************************


const Uint32 Pixel_pack_offs = 0x10U;


///  ****************************************************************


///  VDMA addresses
const Uint32 VDMA_mm2s_addr = 0x5CU;
const Uint32 VDMA_s2mm_addr = 0xACU;

///  VDMA hardware definitions
const Uint32 VDMA_frame_buff = 1U;          /// CHANGE ACCORDING VIVADO PROJECT
const Uint32 VDMA_px_width = 0x1U;          /// bytes

///  VDMA offsets
const Uint32 VDMA_mm2s_cr_offs = 0x00U;
const Uint32 VDMA_mm2s_sr_offs = 0x04U;
const Uint32 VDMA_mm2s_pk_offs = 0x28U;
const Uint32 VDMA_mm2s_hs_offs = 0x54U;
const Uint32 VDMA_mm2s_vs_offs = 0x50U;                 
const Uint32 VDMA_mm2s_st_offs = 0x58U;
const Uint32 VDMA_s2mm_cr_offs = 0x30U;
const Uint32 VDMA_s2mm_sr_offs = 0x34U;
const Uint32 VDMA_s2mm_hs_offs = 0xA4U;
const Uint32 VDMA_s2mm_vs_offs = 0xA0U;                 
const Uint32 VDMA_s2mm_st_offs = 0xA8U;
const Uint32 VDMA_srt_offs = 0x04U;
const Uint32 VDMA_ch_offs = 0x30U;
const Uint32 VDMA_ch_B_offs = 0x50U;

///  VDMA interrupts
const Uint32 VDMA_cnt_irq = 12U;
const Uint32 VDMA_irq_en = 0x1000U;

///  VDMA configuration
const Uint32 VDMA_rs = 0x1U;
const Uint32 VDMA_circ_prk = 0x2U;
const Uint32 VDMA_reset = 0x4U;
const Uint32 VDMA_fcn_ten = 0x10U;
const Uint32 VDMA_cnt_offs = 16U;
const Uint32 VDMA_conf = (VDMA_circ_prk | VDMA_fcn_ten | VDMA_irq_en);


///  ****************************************************************


const Uint32 CAN_srr_offs =	0x00000000U;        /// Software Reset Register
const Uint32 CAN_msr_offs =	0x00000004U;        /// Mode Select Register
const Uint32 CAN_brpr_offs = 0x00000008U;       /// Baud Rate Prescaler
const Uint32 CAN_btr_offs =	0x0000000CU;        /// Bit Timing Register
const Uint32 CAN_ecr_offs =	0x00000010U;        /// Error Counter Register
const Uint32 CAN_esr_offs =	0x00000014U;        /// Error Status Register
const Uint32 CAN_sr_offs = 0x00000018U;         /// Status Register
const Uint32 CAN_isr_offs =	0x0000001CU;        /// Interrupt Status Register
const Uint32 CAN_ier_offs =	0x00000020U;        /// Interrupt Enable Register
const Uint32 CAN_icr_offs =	0x00000024U;        /// Interrupt Clear Register
const Uint32 CAN_tcr_offs =	0x00000028U;        /// Timestamp Control Register
const Uint32 CAN_wir_offs =	0x0000002CU;        /// Watermark Interrupt Register

/// FIFO offsets
const Uint32 CAN_tFO_id_offs = 0x00000030U;         /// TX FIFO ID
const Uint32 CAN_tFO_dl_offs = 0x00000034U;         /// TX FIFO DLC
const Uint32 CAN_tFO_d1_offs =	0x00000038U;        /// TX FIFO Data Word 1
const Uint32 CAN_tFO_d2_offs = 0x0000003CU;         /// TX FIFO Data Word 2
const Uint32 CAN_rFO_id_offs = 0x00000050U;         /// RX FIFO ID
const Uint32 CAN_rFO_dl_offs = 0x00000054U;         /// RX FIFO DLC
const Uint32 CAN_rFO_d1_offs = 0x00000058U;         /// RX FIFO Data Word 1
const Uint32 CAN_rFO_d2_offs = 0x0000005CU;         /// RX FIFO Data Word 2

/// TX HPB offsets
const Uint32 CAN_HPB_id_offs = 0x00000040U;     /// TX High Priority Buffer ID
const Uint32 CAN_HPB_dl_offs = 0x00000044U;     /// TX High Priority Buffer DLC
const Uint32 CAN_HPB_d1_offs = 0x00000048U;     /// TX High Priority Buf Data 1
const Uint32 CAN_HPB_d2_offs = 0x0000004CU;     /// TX High Priority Buf Data Word 2

/// CAN acceptance filter offsets
const Uint32 CAN_afr_offs = 0x00000060U;         /// Acceptance Filter Register
const Uint32 CAN_afmr1_offs = 0x00000064U;       /// Acceptance Filter Mask 1
const Uint32 CAN_afir1_offs = 0x00000068U;       /// Acceptance Filter ID  1
const Uint32 CAN_afmr2_offs = 0x0000006CU;       /// Acceptance Filter Mask  2
const Uint32 CAN_afir2_offs = 0x00000070U;       /// Acceptance Filter ID 2
const Uint32 CAN_afmr3_offs = 0x00000074U;       /// Acceptance Filter Mask 3
const Uint32 CAN_afir3_offs = 0x00000078U;       /// Acceptance Filter ID 3
const Uint32 CAN_afmr4_offs = 0x0000007CU;       /// Acceptance Filter Mask  4
const Uint32 CAN_afir4_offs = 0x00000080U;       /// Acceptance Filter ID 4

/// Mode Select Register (MSR) Bit Definitions and Masks
const Uint32 CAN_ms_snp_mask = 0x00000004U;     /// Snoop Mode Select
const Uint32 CAN_ms_lbk_mask = 0x00000002U;     /// Loop Back Mode Select
const Uint32 CAN_ms_slp_mask = 0x00000001U;     /// Sleep Mode Select

/// Receive error counter values
const Uint32 CAN_ecr_rc_mask = 0x0000FF00U;         /// Receive Error Counter
const Uint32 CAN_ecr_rc_sft = 8U;                   /// Shift Value for REC
const Uint32 CAN_ecr_tc_mask = 0x000000FFU;         /// Transmit Error Counter

/// Status Register (SR) Bit Definitions and Masks
const Uint32 CAN_sr_sn_mask = 0x00001000U;              /// Snoop Mask
const Uint32 CAN_sr_acf_mask = 0x00000800U;             /// Acceptance Filter busy
const Uint32 CAN_sr_tx_mask = 0x00000400U;              /// TX FIFO is full
const Uint32 CAN_sr_txb_mask = 0x00000200U;             /// TX High Priority Buffer full
const Uint32 CAN_sr_bsy_mask = 0x00000020U;             /// Bus Busy
const Uint32 CAN_sr_nrm_mask = 0x00000008U;             /// Normal Mode
const Uint32 CAN_sr_slp_mask = 0x00000004U;             /// Sleep Mode
const Uint32 CAN_sr_cfg_mask = 0x00000001U;             /// Configuration Mode

/// Software Reset Register (SRR) Bit Definitions and Masks
const Uint32 CAN_srr_cn_mask = 0x00000002U;         /// Can Enable
const Uint32 CAN_srr_rs_mask	= 0x00000001U;      /// Reset

/// Acceptance Filter Register (AFR) Bit Definitions and Masks
const Uint32 CAN_afr_u4_mask = 0x00000008U;     /// Use Acceptance Filter No.4
const Uint32 CAN_afr_u3_mask = 0x00000004U;     /// Use Acceptance Filter No.3
const Uint32 CAN_afr_u2_mask = 0x00000002U;     /// Use Acceptance Filter No.2
const Uint32 CAN_afr_u1_mask = 0x00000001U;     /// Use Acceptance Filter No.1
const Uint32 CAN_afr_ua_mask = (static_cast<Uint32>(CAN_afr_u4_mask) | 
					            static_cast<Uint32>(CAN_afr_u3_mask) | 
					            static_cast<Uint32>(CAN_afr_u2_mask) | 
					            static_cast<Uint32>(CAN_afr_u1_mask));

/// CAN operation modes
const Uint32 CAN_mode_cfg = 0x00000001U;             /// Configuration mode
const Uint32 CAN_mode_nrm = 0x00000002U;             /// Normal mode
const Uint32 CAN_mode_lbk = 0x00000004U;             /// Loop Back mode
const Uint32 CAN_mode_slp = 0x00000008U;             /// Sleep mode
const Uint32 CAN_mode_snp = 0x00000010U;             /// Snoop mode

/// Bit Timing Register (BTR) Bit Definitions and Masks
const Uint32 CAN_btr_sj_mask = 0x00000180U;         /// Synchronization Jump Width
const Uint32 CAN_btr_sj_sft = 7U;	                /// Shift Value for SJW
const Uint32 CAN_btr_t2_mask = 0x00000070U;        /// Time Segment 2
const Uint32 CAN_btr_t2_sft = 4U;	                /// Shift Value for TS2
const Uint32 CAN_btr_t1_mask = 0x0000000FU;        /// Time Segment 1
const Uint32 CAN_afr_en_mask = 0x0000000FU;			///	Get AFR enabled filters mask

/// Interrupt Status/Enable/Clear Register Bit Definitions and Masks
const Uint32 CAN_ix_txe_mask = 0x00004000U;         /// Tx Fifo Empty Interrupt
const Uint32 CAN_ix_txw_mask = 0x00002000U;         /// Tx Fifo Watermark Empty
const Uint32 CAN_ix_rxw_mask = 0x00001000U;         /// Rx FIFO Watermark Full
const Uint32 CAN_ix_wku_mask = 0x00000800U;         /// Wake up Interrupt
const Uint32 CAN_ix_slp_mask = 0x00000400U;         /// Sleep Interrupt
const Uint32 CAN_ix_bso_mask = 0x00000200U;         /// Bus Off Interrupt
const Uint32 CAN_ix_err_mask = 0x00000100U;         /// Error Interrupt
const Uint32 CAN_ix_rxn_mask = 0x00000080U;         /// RX FIFO Not Empty Interrupt
const Uint32 CAN_ix_rxo_mask = 0x00000040U;         /// RX FIFO Overflow Interrupt
const Uint32 CAN_ix_rxu_mask = 0x00000020U;         /// RX FIFO Underflow Interrupt
const Uint32 CAN_ix_rxk_mask = 0x00000010U;         /// New Message Received Intr
const Uint32 CAN_ix_txb_mask = 0x00000008U;         /// TX High Priority Buf Full
const Uint32 CAN_ix_txf_mask = 0x00000004U;         /// TX FIFO Full Interrupt
const Uint32 CAN_ix_txk_mask = 0x00000002U;         /// TX Successful Interrupt
const Uint32 CAN_ix_arb_mask = 0x00000001U;         /// Arbitration Lost Interrupt
const Uint32 CAN_ix_all = (CAN_ix_rxw_mask | CAN_ix_wku_mask | CAN_ix_slp_mask | 
				        CAN_ix_bso_mask | CAN_ix_err_mask | CAN_ix_rxn_mask | CAN_ix_rxo_mask | 
				        CAN_ix_rxu_mask | CAN_ix_rxk_mask  | CAN_ix_txb_mask | CAN_ix_txf_mask | 
                        CAN_ix_txk_mask | CAN_ix_arb_mask);
				
/// CAN Watermark Register (WIR) Bit Definitions and Masks
const Uint32 CAN_wir_f_mask = 0x0000003FU;      /// Rx Full Threshold mask
const Uint32 CAN_wir_e_mask = 0x00003F00U;      /// Tx Empty Threshold mask
const Uint32 CAN_wir_e_shift = 0x00000008U;     /// Tx Empty Threshold shift

/// Callback identifiers used as parameters to XCanPs_SetHandler()
const Uint32 CAN_hand_send = 1U;        /// Handler type for frame sending interrupt
const Uint32 CAN_hand_recv = 2U;        /// Handler type for frame reception interrup
const Uint32 CAN_hand_error = 3U;       /// Handler type for error interrupt
const Uint32 CAN_hand_event = 4U;       /// Handler type for all other interrupts

const long sts_device_busy = 21L;	    /// Device is busy
const long sts_err_cnt_max = 22L;	    /// The error counters of a device have maxed out
const long sts_FFO_no_room = 11L;	    /// A FIFO did not have room to put the specified data into
const long sts_no_data = 13L;	        /// There was no data available
const long sts_inv_param = 15L;	        /// An invalid parameter was passed into the function

/// CAN Frame Identifier (  TX High Priority Buffer/TX/RX/Acceptance Filter
///			                Mask/Acceptance Filter ID)
const Uint32 CAN_id_id1_mask = 0xFFE00000U;         /// Standard Messg Identifier
const Uint32 CAN_id_id1_sft = 21U;	                /// Shift Value for id1
const Uint32 CAN_id_srr_mask = 0x00100000U;         /// Substitute Remote TX Req
const Uint32 CAN_id_srr_sft = 20U;	                /// Shift Value for SRR
const Uint32 CAN_id_ide_mask = 0x00080000U;         /// Identifier Extension
const Uint32 CAN_id_ide_sft = 19U;	                /// Shift Value for idE
const Uint32 CAN_id_id2_mask = 0x0007FFFEU;         /// Extended Message Ident
const Uint32 CAN_id_id2_sft = 1U;	                /// Shift Value for id2
const Uint32 CAN_id_rtr_mask = 0x00000001U;         /// Remote TX Request

/// DLC register values
const Uint32 CAN_dlc_mask = 0xF0000000U;	/// Data Length Code
const Uint32 CAN_dlc_sft = 28U;		        /// Shift Value for DLC

/// CAN addresses and frequency
const Uint32 CAN0_baseaddr = 0xFF060000U;
const Uint32 CAN0_highaddr = 0xFF06FFFFU;
const Uint32 CAN1_baseaddr = 0xFF070000U;
const Uint32 CAN1_highaddr = 0xFF07FFFFU;
const Uint32 CAN_CLK_freq = 100000000U;

const Uint32 CAN_st_id_mask = 0x07FFU;			///	Standard ID message mask
const Uint32 CAN_ex_id_mask = 0x1FFFF800U;		///	Extended ID mask
const Uint32 CAN_ext_shift = 11U;
const Uint32 CAN_dlc_ts_mask = 0x0000FFFFU;		///	CAN DLC timestamp mask

const Uint32 CAN_iso_jw_val = 3U;
const Uint32 CAN_iso_ts1_val = 15U;
const Uint32 CAN_iso_ts2_val = 2U;
const Uint32 CAN_iso_prs_val = 29U;
const Uint32 CAN_data_len = 2U;

///  ****************************************************************


///  Auxiliar values (COPROC wrapper)
const Uint32 color_depth = 8U;
const Real gamma_value	= 1.2;
const Uint32 coproc_frames = 16;
const Uint32 AXI_GPIO_b_addr = 0xB0060000U;
const Uint32 VDMA_bd_addr = 0xB0030000U;
const Uint8 MIPI_pwup = 0U;                     /// EMIO pin 0 (bank 3) --> camera

const Uint32 non_valid_rows = 10U;
const Uint32 bytes_per_px = 1U;

/// crop for 1280x980 sensor ROI
const Uint32 video_crop_left = 88U; 
const Uint32 video_crop_top = 54U;
const Uint32 video_sc_width = 1280U; 
const Uint32 video_sc_height = 980U;
const Uint32 wait_time_cam = 500000U;     ///  us

const Uint32 frame_buf_size = 64U * 1024U * 1024U;
const Uint8 cam_id = 4U;
const Uint8 coproc_conf = 5U;
const Uint8 coproc_cl = 0U;
const Uint8 coproc_rw = 1U;
const Uint8 coproc_sc = 2U;
const Uint8 coproc_inv_sc = 3U;
const Uint8 coproc_bit_dis = 14U;

const Uint32 coproc_bit_wd = 8U;
const Uint32 coproc_wid_offs = 4U;
const Uint32 coproc_scl_offs = 8U;
const Uint32 coproc_inv_offs = 12U;
const Uint32 coproc_cam_offs = 16U;

const Uint32 coproc_rst_t = 500U;


///  ****************************************************************


#endif