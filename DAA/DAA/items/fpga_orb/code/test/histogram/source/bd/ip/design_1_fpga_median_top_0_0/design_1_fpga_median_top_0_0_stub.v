// Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2020.1 (lin64) Build 2902540 Wed May 27 19:54:35 MDT 2020
// Date        : Thu Jun 20 09:13:26 2024
// Host        : user-VirtualBox running 64-bit Ubuntu 18.04.6 LTS
// Command     : write_verilog -force -mode synth_stub
//               /home/vmm6/projects_shared/Vision/repo/DAA/items/fpga_orb/code/test/histogram/source/bd/ip/design_1_fpga_median_top_0_0/design_1_fpga_median_top_0_0_stub.v
// Design      : design_1_fpga_median_top_0_0
// Purpose     : Stub declaration of top-level module interface
// Device      : xczu15eg-ffvb1156-2-i
// --------------------------------------------------------------------------------

// This empty module with port declaration file causes synthesis tools to infer a black box for IP.
// The synthesis directives are for Synopsys Synplify support to prevent IO buffer insertion.
// Please paste the declaration into a Verilog source file or add the file as an additional source.
(* X_CORE_INFO = "fpga_median_top,Vivado 2020.1" *)
module design_1_fpga_median_top_0_0(s_axis_tready, s_axis_clk, s_axis_tvalid, 
  s_axis_tlast, s_axis_tdata, m_axis_clk, m_axis_tready, m_axis_tvalid, m_axis_tlast, 
  m_axis_tstrb, m_axis_tdata)
/* synthesis syn_black_box black_box_pad_pin="s_axis_tready,s_axis_clk,s_axis_tvalid,s_axis_tlast,s_axis_tdata[31:0],m_axis_clk,m_axis_tready,m_axis_tvalid,m_axis_tlast,m_axis_tstrb[3:0],m_axis_tdata[7:0]" */;
  output s_axis_tready;
  input s_axis_clk;
  input s_axis_tvalid;
  input s_axis_tlast;
  input [31:0]s_axis_tdata;
  input m_axis_clk;
  input m_axis_tready;
  output m_axis_tvalid;
  output m_axis_tlast;
  output [3:0]m_axis_tstrb;
  output [7:0]m_axis_tdata;
endmodule
