//Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2020.1 (lin64) Build 2902540 Wed May 27 19:54:35 MDT 2020
//Date        : Mon Aug 25 11:49:08 2025
//Host        : Petalinux-Vivado2020 running 64-bit Ubuntu 18.04.6 LTS
//Command     : generate_target design_1_wrapper.bd
//Design      : design_1_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module design_1_wrapper
   (CAN_0_0_rx,
    CAN_0_0_tx,
    CAN_1_0_rx,
    CAN_1_0_tx,
    GPIO_0_0_tri_io,
    IIC_2_scl_io,
    IIC_2_sda_io,
    UART_0_0_rxd,
    UART_0_0_txd,
    mipi_phy_if_0_clk_n,
    mipi_phy_if_0_clk_p,
    mipi_phy_if_0_data_n,
    mipi_phy_if_0_data_p);
  input CAN_0_0_rx;
  output CAN_0_0_tx;
  input CAN_1_0_rx;
  output CAN_1_0_tx;
  inout [8:0]GPIO_0_0_tri_io;
  inout IIC_2_scl_io;
  inout IIC_2_sda_io;
  input UART_0_0_rxd;
  output UART_0_0_txd;
  input mipi_phy_if_0_clk_n;
  input mipi_phy_if_0_clk_p;
  input [0:0]mipi_phy_if_0_data_n;
  input [0:0]mipi_phy_if_0_data_p;

  wire CAN_0_0_rx;
  wire CAN_0_0_tx;
  wire CAN_1_0_rx;
  wire CAN_1_0_tx;
  wire [0:0]GPIO_0_0_tri_i_0;
  wire [1:1]GPIO_0_0_tri_i_1;
  wire [2:2]GPIO_0_0_tri_i_2;
  wire [3:3]GPIO_0_0_tri_i_3;
  wire [4:4]GPIO_0_0_tri_i_4;
  wire [5:5]GPIO_0_0_tri_i_5;
  wire [6:6]GPIO_0_0_tri_i_6;
  wire [7:7]GPIO_0_0_tri_i_7;
  wire [8:8]GPIO_0_0_tri_i_8;
  wire [0:0]GPIO_0_0_tri_io_0;
  wire [1:1]GPIO_0_0_tri_io_1;
  wire [2:2]GPIO_0_0_tri_io_2;
  wire [3:3]GPIO_0_0_tri_io_3;
  wire [4:4]GPIO_0_0_tri_io_4;
  wire [5:5]GPIO_0_0_tri_io_5;
  wire [6:6]GPIO_0_0_tri_io_6;
  wire [7:7]GPIO_0_0_tri_io_7;
  wire [8:8]GPIO_0_0_tri_io_8;
  wire [0:0]GPIO_0_0_tri_o_0;
  wire [1:1]GPIO_0_0_tri_o_1;
  wire [2:2]GPIO_0_0_tri_o_2;
  wire [3:3]GPIO_0_0_tri_o_3;
  wire [4:4]GPIO_0_0_tri_o_4;
  wire [5:5]GPIO_0_0_tri_o_5;
  wire [6:6]GPIO_0_0_tri_o_6;
  wire [7:7]GPIO_0_0_tri_o_7;
  wire [8:8]GPIO_0_0_tri_o_8;
  wire [0:0]GPIO_0_0_tri_t_0;
  wire [1:1]GPIO_0_0_tri_t_1;
  wire [2:2]GPIO_0_0_tri_t_2;
  wire [3:3]GPIO_0_0_tri_t_3;
  wire [4:4]GPIO_0_0_tri_t_4;
  wire [5:5]GPIO_0_0_tri_t_5;
  wire [6:6]GPIO_0_0_tri_t_6;
  wire [7:7]GPIO_0_0_tri_t_7;
  wire [8:8]GPIO_0_0_tri_t_8;
  wire IIC_2_scl_i;
  wire IIC_2_scl_io;
  wire IIC_2_scl_o;
  wire IIC_2_scl_t;
  wire IIC_2_sda_i;
  wire IIC_2_sda_io;
  wire IIC_2_sda_o;
  wire IIC_2_sda_t;
  wire UART_0_0_rxd;
  wire UART_0_0_txd;
  wire mipi_phy_if_0_clk_n;
  wire mipi_phy_if_0_clk_p;
  wire [0:0]mipi_phy_if_0_data_n;
  wire [0:0]mipi_phy_if_0_data_p;

  IOBUF GPIO_0_0_tri_iobuf_0
       (.I(GPIO_0_0_tri_o_0),
        .IO(GPIO_0_0_tri_io[0]),
        .O(GPIO_0_0_tri_i_0),
        .T(GPIO_0_0_tri_t_0));
  IOBUF GPIO_0_0_tri_iobuf_1
       (.I(GPIO_0_0_tri_o_1),
        .IO(GPIO_0_0_tri_io[1]),
        .O(GPIO_0_0_tri_i_1),
        .T(GPIO_0_0_tri_t_1));
  IOBUF GPIO_0_0_tri_iobuf_2
       (.I(GPIO_0_0_tri_o_2),
        .IO(GPIO_0_0_tri_io[2]),
        .O(GPIO_0_0_tri_i_2),
        .T(GPIO_0_0_tri_t_2));
  IOBUF GPIO_0_0_tri_iobuf_3
       (.I(GPIO_0_0_tri_o_3),
        .IO(GPIO_0_0_tri_io[3]),
        .O(GPIO_0_0_tri_i_3),
        .T(GPIO_0_0_tri_t_3));
  IOBUF GPIO_0_0_tri_iobuf_4
       (.I(GPIO_0_0_tri_o_4),
        .IO(GPIO_0_0_tri_io[4]),
        .O(GPIO_0_0_tri_i_4),
        .T(GPIO_0_0_tri_t_4));
  IOBUF GPIO_0_0_tri_iobuf_5
       (.I(GPIO_0_0_tri_o_5),
        .IO(GPIO_0_0_tri_io[5]),
        .O(GPIO_0_0_tri_i_5),
        .T(GPIO_0_0_tri_t_5));
  IOBUF GPIO_0_0_tri_iobuf_6
       (.I(GPIO_0_0_tri_o_6),
        .IO(GPIO_0_0_tri_io[6]),
        .O(GPIO_0_0_tri_i_6),
        .T(GPIO_0_0_tri_t_6));
  IOBUF GPIO_0_0_tri_iobuf_7
       (.I(GPIO_0_0_tri_o_7),
        .IO(GPIO_0_0_tri_io[7]),
        .O(GPIO_0_0_tri_i_7),
        .T(GPIO_0_0_tri_t_7));
  IOBUF GPIO_0_0_tri_iobuf_8
       (.I(GPIO_0_0_tri_o_8),
        .IO(GPIO_0_0_tri_io[8]),
        .O(GPIO_0_0_tri_i_8),
        .T(GPIO_0_0_tri_t_8));
  IOBUF IIC_2_scl_iobuf
       (.I(IIC_2_scl_o),
        .IO(IIC_2_scl_io),
        .O(IIC_2_scl_i),
        .T(IIC_2_scl_t));
  IOBUF IIC_2_sda_iobuf
       (.I(IIC_2_sda_o),
        .IO(IIC_2_sda_io),
        .O(IIC_2_sda_i),
        .T(IIC_2_sda_t));
  design_1 design_1_i
       (.CAN_0_0_rx(CAN_0_0_rx),
        .CAN_0_0_tx(CAN_0_0_tx),
        .CAN_1_0_rx(CAN_1_0_rx),
        .CAN_1_0_tx(CAN_1_0_tx),
        .GPIO_0_0_tri_i({GPIO_0_0_tri_i_8,GPIO_0_0_tri_i_7,GPIO_0_0_tri_i_6,GPIO_0_0_tri_i_5,GPIO_0_0_tri_i_4,GPIO_0_0_tri_i_3,GPIO_0_0_tri_i_2,GPIO_0_0_tri_i_1,GPIO_0_0_tri_i_0}),
        .GPIO_0_0_tri_o({GPIO_0_0_tri_o_8,GPIO_0_0_tri_o_7,GPIO_0_0_tri_o_6,GPIO_0_0_tri_o_5,GPIO_0_0_tri_o_4,GPIO_0_0_tri_o_3,GPIO_0_0_tri_o_2,GPIO_0_0_tri_o_1,GPIO_0_0_tri_o_0}),
        .GPIO_0_0_tri_t({GPIO_0_0_tri_t_8,GPIO_0_0_tri_t_7,GPIO_0_0_tri_t_6,GPIO_0_0_tri_t_5,GPIO_0_0_tri_t_4,GPIO_0_0_tri_t_3,GPIO_0_0_tri_t_2,GPIO_0_0_tri_t_1,GPIO_0_0_tri_t_0}),
        .IIC_2_scl_i(IIC_2_scl_i),
        .IIC_2_scl_o(IIC_2_scl_o),
        .IIC_2_scl_t(IIC_2_scl_t),
        .IIC_2_sda_i(IIC_2_sda_i),
        .IIC_2_sda_o(IIC_2_sda_o),
        .IIC_2_sda_t(IIC_2_sda_t),
        .UART_0_0_rxd(UART_0_0_rxd),
        .UART_0_0_txd(UART_0_0_txd),
        .mipi_phy_if_0_clk_n(mipi_phy_if_0_clk_n),
        .mipi_phy_if_0_clk_p(mipi_phy_if_0_clk_p),
        .mipi_phy_if_0_data_n(mipi_phy_if_0_data_n),
        .mipi_phy_if_0_data_p(mipi_phy_if_0_data_p));
endmodule
