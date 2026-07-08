//Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2020.1 (lin64) Build 2902540 Wed May 27 19:54:35 MDT 2020
//Date        : Thu Apr 24 10:27:25 2025
//Host        : user-VirtualBox running 64-bit Ubuntu 18.04.6 LTS
//Command     : generate_target design_1_wrapper.bd
//Design      : design_1_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module design_1_wrapper
   (cam_gpio,
    cam_i2c_scl_io,
    cam_i2c_sda_io,
    dbg0,
    dbg1,
    mipi_phy_if_0_clk_n,
    mipi_phy_if_0_clk_p,
    mipi_phy_if_0_data_n,
    mipi_phy_if_0_data_p,
    xtrig);
  output [0:0]cam_gpio;
  inout cam_i2c_scl_io;
  inout cam_i2c_sda_io;
  output [0:0]dbg0;
  output [0:0]dbg1;
  input mipi_phy_if_0_clk_n;
  input mipi_phy_if_0_clk_p;
  input [0:0]mipi_phy_if_0_data_n;
  input [0:0]mipi_phy_if_0_data_p;
  output [0:0]xtrig;

  wire [0:0]cam_gpio;
  wire cam_i2c_scl_i;
  wire cam_i2c_scl_io;
  wire cam_i2c_scl_o;
  wire cam_i2c_scl_t;
  wire cam_i2c_sda_i;
  wire cam_i2c_sda_io;
  wire cam_i2c_sda_o;
  wire cam_i2c_sda_t;
  wire [0:0]dbg0;
  wire [0:0]dbg1;
  wire mipi_phy_if_0_clk_n;
  wire mipi_phy_if_0_clk_p;
  wire [0:0]mipi_phy_if_0_data_n;
  wire [0:0]mipi_phy_if_0_data_p;
  wire [0:0]xtrig;

  IOBUF cam_i2c_scl_iobuf
       (.I(cam_i2c_scl_o),
        .IO(cam_i2c_scl_io),
        .O(cam_i2c_scl_i),
        .T(cam_i2c_scl_t));
  IOBUF cam_i2c_sda_iobuf
       (.I(cam_i2c_sda_o),
        .IO(cam_i2c_sda_io),
        .O(cam_i2c_sda_i),
        .T(cam_i2c_sda_t));
  design_1 design_1_i
       (.cam_gpio(cam_gpio),
        .cam_i2c_scl_i(cam_i2c_scl_i),
        .cam_i2c_scl_o(cam_i2c_scl_o),
        .cam_i2c_scl_t(cam_i2c_scl_t),
        .cam_i2c_sda_i(cam_i2c_sda_i),
        .cam_i2c_sda_o(cam_i2c_sda_o),
        .cam_i2c_sda_t(cam_i2c_sda_t),
        .dbg0(dbg0),
        .dbg1(dbg1),
        .mipi_phy_if_0_clk_n(mipi_phy_if_0_clk_n),
        .mipi_phy_if_0_clk_p(mipi_phy_if_0_clk_p),
        .mipi_phy_if_0_data_n(mipi_phy_if_0_data_n),
        .mipi_phy_if_0_data_p(mipi_phy_if_0_data_p),
        .xtrig(xtrig));
endmodule
