//Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
//Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
//--------------------------------------------------------------------------------
//Tool Version: Vivado v.2023.1 (lin64) Build 3865809 Sun May  7 15:04:56 MDT 2023
//Date        : Thu Jun 11 11:49:41 2026
//Host        : EMB01091-IJM1 running 64-bit Ubuntu 24.04.3 LTS
//Command     : generate_target design_1_wrapper.bd
//Design      : design_1_wrapper
//Purpose     : IP block netlist
//--------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

module design_1_wrapper
   (mipi_phy_if_0_clk_n,
    mipi_phy_if_0_clk_p,
    mipi_phy_if_0_data_n,
    mipi_phy_if_0_data_p);
  output mipi_phy_if_0_clk_n;
  output mipi_phy_if_0_clk_p;
  output [0:0]mipi_phy_if_0_data_n;
  output [0:0]mipi_phy_if_0_data_p;

  wire mipi_phy_if_0_clk_n;
  wire mipi_phy_if_0_clk_p;
  wire [0:0]mipi_phy_if_0_data_n;
  wire [0:0]mipi_phy_if_0_data_p;

  design_1 design_1_i
       (.mipi_phy_if_0_clk_n(mipi_phy_if_0_clk_n),
        .mipi_phy_if_0_clk_p(mipi_phy_if_0_clk_p),
        .mipi_phy_if_0_data_n(mipi_phy_if_0_data_n),
        .mipi_phy_if_0_data_p(mipi_phy_if_0_data_p));
endmodule
