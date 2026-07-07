// Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
// --------------------------------------------------------------------------------
// Tool Version: Vivado v.2020.1 (lin64) Build 2902540 Wed May 27 19:54:35 MDT 2020
// Date        : Thu Jun 20 09:13:26 2024
// Host        : user-VirtualBox running 64-bit Ubuntu 18.04.6 LTS
// Command     : write_verilog -force -mode funcsim
//               /home/vmm6/projects_shared/Vision/repo/DAA/items/fpga_orb/code/test/histogram/source/bd/ip/design_1_fpga_median_top_0_0/design_1_fpga_median_top_0_0_sim_netlist.v
// Design      : design_1_fpga_median_top_0_0
// Purpose     : This verilog netlist is a functional simulation representation of the design and should not be modified
//               or synthesized. This netlist cannot be used for SDF annotated simulation.
// Device      : xczu15eg-ffvb1156-2-i
// --------------------------------------------------------------------------------
`timescale 1 ps / 1 ps

(* CHECK_LICENSE_TYPE = "design_1_fpga_median_top_0_0,fpga_median_top,{}" *) (* DowngradeIPIdentifiedWarnings = "yes" *) (* IP_DEFINITION_SOURCE = "module_ref" *) 
(* X_CORE_INFO = "fpga_median_top,Vivado 2020.1" *) 
(* NotValidForBitStream *)
module design_1_fpga_median_top_0_0
   (s_axis_tready,
    s_axis_clk,
    s_axis_tvalid,
    s_axis_tlast,
    s_axis_tdata,
    m_axis_clk,
    m_axis_tready,
    m_axis_tvalid,
    m_axis_tlast,
    m_axis_tstrb,
    m_axis_tdata);
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TREADY" *) output s_axis_tready;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 s_axis_clk CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axis_clk, ASSOCIATED_BUSIF s_axis, FREQ_HZ 150000000, FREQ_TOLERANCE_HZ 0, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, INSERT_VIP 0" *) input s_axis_clk;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TVALID" *) input s_axis_tvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TLAST" *) input s_axis_tlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 s_axis TDATA" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME s_axis, TDATA_NUM_BYTES 4, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 0, HAS_TKEEP 0, HAS_TLAST 1, FREQ_HZ 150000000, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, LAYERED_METADATA undef, INSERT_VIP 0" *) input [31:0]s_axis_tdata;
  (* X_INTERFACE_INFO = "xilinx.com:signal:clock:1.0 m_axis_clk CLK" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME m_axis_clk, ASSOCIATED_BUSIF m_axis, FREQ_HZ 150000000, FREQ_TOLERANCE_HZ 0, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, INSERT_VIP 0" *) input m_axis_clk;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TREADY" *) input m_axis_tready;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TVALID" *) output m_axis_tvalid;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TLAST" *) output m_axis_tlast;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TSTRB" *) output [3:0]m_axis_tstrb;
  (* X_INTERFACE_INFO = "xilinx.com:interface:axis:1.0 m_axis TDATA" *) (* X_INTERFACE_PARAMETER = "XIL_INTERFACENAME m_axis, TDATA_NUM_BYTES 1, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 1, HAS_TKEEP 0, HAS_TLAST 1, FREQ_HZ 150000000, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, LAYERED_METADATA undef, INSERT_VIP 0" *) output [7:0]m_axis_tdata;

  wire \<const1> ;
  wire m_axis_clk;
  wire [7:0]m_axis_tdata;
  wire m_axis_tlast;
  wire m_axis_tready;
  wire s_axis_clk;
  wire [31:0]s_axis_tdata;
  wire s_axis_tlast;
  wire s_axis_tready;
  wire s_axis_tvalid;

  assign m_axis_tstrb[3] = \<const1> ;
  assign m_axis_tstrb[2] = \<const1> ;
  assign m_axis_tstrb[1] = \<const1> ;
  assign m_axis_tstrb[0] = \<const1> ;
  assign m_axis_tvalid = m_axis_tlast;
  VCC VCC
       (.P(\<const1> ));
  design_1_fpga_median_top_0_0_fpga_median_top inst
       (.m_axis_clk(m_axis_clk),
        .m_axis_tdata(m_axis_tdata),
        .m_axis_tlast(m_axis_tlast),
        .m_axis_tready(m_axis_tready),
        .s_axis_clk(s_axis_clk),
        .s_axis_tdata(s_axis_tdata),
        .s_axis_tlast(s_axis_tlast),
        .s_axis_tready(s_axis_tready),
        .s_axis_tvalid(s_axis_tvalid));
endmodule

(* ORIG_REF_NAME = "fpga_median_top" *) 
module design_1_fpga_median_top_0_0_fpga_median_top
   (m_axis_tdata,
    s_axis_tready,
    m_axis_tlast,
    s_axis_tvalid,
    s_axis_clk,
    s_axis_tdata,
    m_axis_clk,
    s_axis_tlast,
    m_axis_tready);
  output [7:0]m_axis_tdata;
  output s_axis_tready;
  output m_axis_tlast;
  input s_axis_tvalid;
  input s_axis_clk;
  input [31:0]s_axis_tdata;
  input m_axis_clk;
  input s_axis_tlast;
  input m_axis_tready;

  wire \FSM_onehot_s_state[2]_i_1_n_0 ;
  wire \FSM_onehot_s_state[2]_i_2_n_0 ;
  wire \FSM_onehot_s_state_reg_n_0_[0] ;
  wire \FSM_onehot_s_state_reg_n_0_[2] ;
  wire data0;
  wire [31:0]hist_acc;
  wire hist_acc0_carry__0_i_1_n_0;
  wire hist_acc0_carry__0_i_2_n_0;
  wire hist_acc0_carry__0_i_3_n_0;
  wire hist_acc0_carry__0_i_4_n_0;
  wire hist_acc0_carry__0_i_5_n_0;
  wire hist_acc0_carry__0_i_6_n_0;
  wire hist_acc0_carry__0_i_7_n_0;
  wire hist_acc0_carry__0_i_8_n_0;
  wire hist_acc0_carry__0_n_0;
  wire hist_acc0_carry__0_n_1;
  wire hist_acc0_carry__0_n_2;
  wire hist_acc0_carry__0_n_3;
  wire hist_acc0_carry__0_n_4;
  wire hist_acc0_carry__0_n_5;
  wire hist_acc0_carry__0_n_6;
  wire hist_acc0_carry__0_n_7;
  wire hist_acc0_carry__1_i_1_n_0;
  wire hist_acc0_carry__1_i_2_n_0;
  wire hist_acc0_carry__1_i_3_n_0;
  wire hist_acc0_carry__1_i_4_n_0;
  wire hist_acc0_carry__1_i_5_n_0;
  wire hist_acc0_carry__1_i_6_n_0;
  wire hist_acc0_carry__1_i_7_n_0;
  wire hist_acc0_carry__1_i_8_n_0;
  wire hist_acc0_carry__1_n_0;
  wire hist_acc0_carry__1_n_1;
  wire hist_acc0_carry__1_n_2;
  wire hist_acc0_carry__1_n_3;
  wire hist_acc0_carry__1_n_4;
  wire hist_acc0_carry__1_n_5;
  wire hist_acc0_carry__1_n_6;
  wire hist_acc0_carry__1_n_7;
  wire hist_acc0_carry__2_i_1_n_0;
  wire hist_acc0_carry__2_i_2_n_0;
  wire hist_acc0_carry__2_i_3_n_0;
  wire hist_acc0_carry__2_i_4_n_0;
  wire hist_acc0_carry__2_i_5_n_0;
  wire hist_acc0_carry__2_i_6_n_0;
  wire hist_acc0_carry__2_i_7_n_0;
  wire hist_acc0_carry__2_i_8_n_0;
  wire hist_acc0_carry__2_n_1;
  wire hist_acc0_carry__2_n_2;
  wire hist_acc0_carry__2_n_3;
  wire hist_acc0_carry__2_n_4;
  wire hist_acc0_carry__2_n_5;
  wire hist_acc0_carry__2_n_6;
  wire hist_acc0_carry__2_n_7;
  wire hist_acc0_carry_i_1_n_0;
  wire hist_acc0_carry_i_2_n_0;
  wire hist_acc0_carry_i_3_n_0;
  wire hist_acc0_carry_i_4_n_0;
  wire hist_acc0_carry_i_5_n_0;
  wire hist_acc0_carry_i_6_n_0;
  wire hist_acc0_carry_i_7_n_0;
  wire hist_acc0_carry_i_8_n_0;
  wire hist_acc0_carry_n_0;
  wire hist_acc0_carry_n_1;
  wire hist_acc0_carry_n_2;
  wire hist_acc0_carry_n_3;
  wire hist_acc0_carry_n_4;
  wire hist_acc0_carry_n_5;
  wire hist_acc0_carry_n_6;
  wire hist_acc0_carry_n_7;
  wire \hist_acc[31]_i_1_n_0 ;
  wire hist_acc_2;
  wire [7:0]hist_idx;
  wire \hist_idx[7]_i_2_n_0 ;
  wire [7:0]hist_median;
  wire hist_median_1;
  wire [31:0]hist_value;
  wire hist_value_0;
  wire [31:0]in3;
  wire [7:0]in4;
  wire m_axis_clk;
  wire [7:0]m_axis_tdata;
  wire m_axis_tlast;
  wire m_axis_tready;
  wire m_axis_tvalid_i_1_n_0;
  wire m_state_i_1_n_0;
  wire m_state_reg_n_0;
  wire s_axis_clk;
  wire [31:0]s_axis_tdata;
  wire s_axis_tlast;
  wire s_axis_tready;
  wire s_axis_tready_i_1_n_0;
  wire s_axis_tvalid;
  wire s_state1_carry__0_i_10_n_0;
  wire s_state1_carry__0_i_11_n_0;
  wire s_state1_carry__0_i_12_n_0;
  wire s_state1_carry__0_i_13_n_0;
  wire s_state1_carry__0_i_14_n_0;
  wire s_state1_carry__0_i_15_n_0;
  wire s_state1_carry__0_i_16_n_0;
  wire s_state1_carry__0_i_1_n_0;
  wire s_state1_carry__0_i_2_n_0;
  wire s_state1_carry__0_i_3_n_0;
  wire s_state1_carry__0_i_4_n_0;
  wire s_state1_carry__0_i_5_n_0;
  wire s_state1_carry__0_i_6_n_0;
  wire s_state1_carry__0_i_7_n_0;
  wire s_state1_carry__0_i_8_n_0;
  wire s_state1_carry__0_i_9_n_0;
  wire s_state1_carry__0_n_0;
  wire s_state1_carry__0_n_1;
  wire s_state1_carry__0_n_2;
  wire s_state1_carry__0_n_3;
  wire s_state1_carry__0_n_4;
  wire s_state1_carry__0_n_5;
  wire s_state1_carry__0_n_6;
  wire s_state1_carry__0_n_7;
  wire s_state1_carry_i_10_n_0;
  wire s_state1_carry_i_11_n_0;
  wire s_state1_carry_i_12_n_0;
  wire s_state1_carry_i_13_n_0;
  wire s_state1_carry_i_14_n_0;
  wire s_state1_carry_i_15_n_0;
  wire s_state1_carry_i_16_n_0;
  wire s_state1_carry_i_1_n_0;
  wire s_state1_carry_i_2_n_0;
  wire s_state1_carry_i_3_n_0;
  wire s_state1_carry_i_4_n_0;
  wire s_state1_carry_i_5_n_0;
  wire s_state1_carry_i_6_n_0;
  wire s_state1_carry_i_7_n_0;
  wire s_state1_carry_i_8_n_0;
  wire s_state1_carry_i_9_n_0;
  wire s_state1_carry_n_0;
  wire s_state1_carry_n_1;
  wire s_state1_carry_n_2;
  wire s_state1_carry_n_3;
  wire s_state1_carry_n_4;
  wire s_state1_carry_n_5;
  wire s_state1_carry_n_6;
  wire s_state1_carry_n_7;
  wire start_read;
  wire start_read_i_1_n_0;
  wire start_write_i_1_n_0;
  wire start_write_reg_n_0;
  wire [7:7]NLW_hist_acc0_carry__2_CO_UNCONNECTED;
  wire [7:0]NLW_s_state1_carry_O_UNCONNECTED;
  wire [7:0]NLW_s_state1_carry__0_O_UNCONNECTED;

  LUT5 #(
    .INIT(32'hFEFEFEEE)) 
    \FSM_onehot_s_state[2]_i_1 
       (.I0(\FSM_onehot_s_state_reg_n_0_[2] ),
        .I1(\FSM_onehot_s_state[2]_i_2_n_0 ),
        .I2(hist_value_0),
        .I3(s_state1_carry__0_n_0),
        .I4(s_axis_tlast),
        .O(\FSM_onehot_s_state[2]_i_1_n_0 ));
  (* SOFT_HLUTNM = "soft_lutpair1" *) 
  LUT3 #(
    .INIT(8'h80)) 
    \FSM_onehot_s_state[2]_i_2 
       (.I0(\FSM_onehot_s_state_reg_n_0_[0] ),
        .I1(start_read),
        .I2(s_axis_tvalid),
        .O(\FSM_onehot_s_state[2]_i_2_n_0 ));
  (* FSM_ENCODED_STATES = "idle:001,calc:010,save:100," *) 
  FDRE #(
    .INIT(1'b1)) 
    \FSM_onehot_s_state_reg[0] 
       (.C(s_axis_clk),
        .CE(\FSM_onehot_s_state[2]_i_1_n_0 ),
        .D(\FSM_onehot_s_state_reg_n_0_[2] ),
        .Q(\FSM_onehot_s_state_reg_n_0_[0] ),
        .R(1'b0));
  (* FSM_ENCODED_STATES = "idle:001,calc:010,save:100," *) 
  FDRE #(
    .INIT(1'b0)) 
    \FSM_onehot_s_state_reg[1] 
       (.C(s_axis_clk),
        .CE(\FSM_onehot_s_state[2]_i_1_n_0 ),
        .D(\FSM_onehot_s_state_reg_n_0_[0] ),
        .Q(hist_value_0),
        .R(1'b0));
  (* FSM_ENCODED_STATES = "idle:001,calc:010,save:100," *) 
  FDRE #(
    .INIT(1'b0)) 
    \FSM_onehot_s_state_reg[2] 
       (.C(s_axis_clk),
        .CE(\FSM_onehot_s_state[2]_i_1_n_0 ),
        .D(hist_value_0),
        .Q(\FSM_onehot_s_state_reg_n_0_[2] ),
        .R(1'b0));
  LUT2 #(
    .INIT(4'h8)) 
    \data[7]_i_1 
       (.I0(m_axis_tready),
        .I1(m_state_reg_n_0),
        .O(data0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[0] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[0]),
        .Q(m_axis_tdata[0]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[1] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[1]),
        .Q(m_axis_tdata[1]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[2] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[2]),
        .Q(m_axis_tdata[2]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[3] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[3]),
        .Q(m_axis_tdata[3]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[4] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[4]),
        .Q(m_axis_tdata[4]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[5] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[5]),
        .Q(m_axis_tdata[5]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[6] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[6]),
        .Q(m_axis_tdata[6]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \data_reg[7] 
       (.C(m_axis_clk),
        .CE(data0),
        .D(hist_median[7]),
        .Q(m_axis_tdata[7]),
        .R(1'b0));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 hist_acc0_carry
       (.CI(1'b0),
        .CI_TOP(1'b0),
        .CO({hist_acc0_carry_n_0,hist_acc0_carry_n_1,hist_acc0_carry_n_2,hist_acc0_carry_n_3,hist_acc0_carry_n_4,hist_acc0_carry_n_5,hist_acc0_carry_n_6,hist_acc0_carry_n_7}),
        .DI(hist_acc[7:0]),
        .O(in3[7:0]),
        .S({hist_acc0_carry_i_1_n_0,hist_acc0_carry_i_2_n_0,hist_acc0_carry_i_3_n_0,hist_acc0_carry_i_4_n_0,hist_acc0_carry_i_5_n_0,hist_acc0_carry_i_6_n_0,hist_acc0_carry_i_7_n_0,hist_acc0_carry_i_8_n_0}));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 hist_acc0_carry__0
       (.CI(hist_acc0_carry_n_0),
        .CI_TOP(1'b0),
        .CO({hist_acc0_carry__0_n_0,hist_acc0_carry__0_n_1,hist_acc0_carry__0_n_2,hist_acc0_carry__0_n_3,hist_acc0_carry__0_n_4,hist_acc0_carry__0_n_5,hist_acc0_carry__0_n_6,hist_acc0_carry__0_n_7}),
        .DI(hist_acc[15:8]),
        .O(in3[15:8]),
        .S({hist_acc0_carry__0_i_1_n_0,hist_acc0_carry__0_i_2_n_0,hist_acc0_carry__0_i_3_n_0,hist_acc0_carry__0_i_4_n_0,hist_acc0_carry__0_i_5_n_0,hist_acc0_carry__0_i_6_n_0,hist_acc0_carry__0_i_7_n_0,hist_acc0_carry__0_i_8_n_0}));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_1
       (.I0(hist_acc[15]),
        .I1(hist_value[15]),
        .O(hist_acc0_carry__0_i_1_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_2
       (.I0(hist_acc[14]),
        .I1(hist_value[14]),
        .O(hist_acc0_carry__0_i_2_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_3
       (.I0(hist_acc[13]),
        .I1(hist_value[13]),
        .O(hist_acc0_carry__0_i_3_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_4
       (.I0(hist_acc[12]),
        .I1(hist_value[12]),
        .O(hist_acc0_carry__0_i_4_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_5
       (.I0(hist_acc[11]),
        .I1(hist_value[11]),
        .O(hist_acc0_carry__0_i_5_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_6
       (.I0(hist_acc[10]),
        .I1(hist_value[10]),
        .O(hist_acc0_carry__0_i_6_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_7
       (.I0(hist_acc[9]),
        .I1(hist_value[9]),
        .O(hist_acc0_carry__0_i_7_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__0_i_8
       (.I0(hist_acc[8]),
        .I1(hist_value[8]),
        .O(hist_acc0_carry__0_i_8_n_0));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 hist_acc0_carry__1
       (.CI(hist_acc0_carry__0_n_0),
        .CI_TOP(1'b0),
        .CO({hist_acc0_carry__1_n_0,hist_acc0_carry__1_n_1,hist_acc0_carry__1_n_2,hist_acc0_carry__1_n_3,hist_acc0_carry__1_n_4,hist_acc0_carry__1_n_5,hist_acc0_carry__1_n_6,hist_acc0_carry__1_n_7}),
        .DI(hist_acc[23:16]),
        .O(in3[23:16]),
        .S({hist_acc0_carry__1_i_1_n_0,hist_acc0_carry__1_i_2_n_0,hist_acc0_carry__1_i_3_n_0,hist_acc0_carry__1_i_4_n_0,hist_acc0_carry__1_i_5_n_0,hist_acc0_carry__1_i_6_n_0,hist_acc0_carry__1_i_7_n_0,hist_acc0_carry__1_i_8_n_0}));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_1
       (.I0(hist_acc[23]),
        .I1(hist_value[23]),
        .O(hist_acc0_carry__1_i_1_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_2
       (.I0(hist_acc[22]),
        .I1(hist_value[22]),
        .O(hist_acc0_carry__1_i_2_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_3
       (.I0(hist_acc[21]),
        .I1(hist_value[21]),
        .O(hist_acc0_carry__1_i_3_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_4
       (.I0(hist_acc[20]),
        .I1(hist_value[20]),
        .O(hist_acc0_carry__1_i_4_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_5
       (.I0(hist_acc[19]),
        .I1(hist_value[19]),
        .O(hist_acc0_carry__1_i_5_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_6
       (.I0(hist_acc[18]),
        .I1(hist_value[18]),
        .O(hist_acc0_carry__1_i_6_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_7
       (.I0(hist_acc[17]),
        .I1(hist_value[17]),
        .O(hist_acc0_carry__1_i_7_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__1_i_8
       (.I0(hist_acc[16]),
        .I1(hist_value[16]),
        .O(hist_acc0_carry__1_i_8_n_0));
  (* ADDER_THRESHOLD = "35" *) 
  CARRY8 hist_acc0_carry__2
       (.CI(hist_acc0_carry__1_n_0),
        .CI_TOP(1'b0),
        .CO({NLW_hist_acc0_carry__2_CO_UNCONNECTED[7],hist_acc0_carry__2_n_1,hist_acc0_carry__2_n_2,hist_acc0_carry__2_n_3,hist_acc0_carry__2_n_4,hist_acc0_carry__2_n_5,hist_acc0_carry__2_n_6,hist_acc0_carry__2_n_7}),
        .DI({1'b0,hist_acc[30:24]}),
        .O(in3[31:24]),
        .S({hist_acc0_carry__2_i_1_n_0,hist_acc0_carry__2_i_2_n_0,hist_acc0_carry__2_i_3_n_0,hist_acc0_carry__2_i_4_n_0,hist_acc0_carry__2_i_5_n_0,hist_acc0_carry__2_i_6_n_0,hist_acc0_carry__2_i_7_n_0,hist_acc0_carry__2_i_8_n_0}));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_1
       (.I0(hist_acc[31]),
        .I1(hist_value[31]),
        .O(hist_acc0_carry__2_i_1_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_2
       (.I0(hist_acc[30]),
        .I1(hist_value[30]),
        .O(hist_acc0_carry__2_i_2_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_3
       (.I0(hist_acc[29]),
        .I1(hist_value[29]),
        .O(hist_acc0_carry__2_i_3_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_4
       (.I0(hist_acc[28]),
        .I1(hist_value[28]),
        .O(hist_acc0_carry__2_i_4_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_5
       (.I0(hist_acc[27]),
        .I1(hist_value[27]),
        .O(hist_acc0_carry__2_i_5_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_6
       (.I0(hist_acc[26]),
        .I1(hist_value[26]),
        .O(hist_acc0_carry__2_i_6_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_7
       (.I0(hist_acc[25]),
        .I1(hist_value[25]),
        .O(hist_acc0_carry__2_i_7_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry__2_i_8
       (.I0(hist_acc[24]),
        .I1(hist_value[24]),
        .O(hist_acc0_carry__2_i_8_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_1
       (.I0(hist_acc[7]),
        .I1(hist_value[7]),
        .O(hist_acc0_carry_i_1_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_2
       (.I0(hist_acc[6]),
        .I1(hist_value[6]),
        .O(hist_acc0_carry_i_2_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_3
       (.I0(hist_acc[5]),
        .I1(hist_value[5]),
        .O(hist_acc0_carry_i_3_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_4
       (.I0(hist_acc[4]),
        .I1(hist_value[4]),
        .O(hist_acc0_carry_i_4_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_5
       (.I0(hist_acc[3]),
        .I1(hist_value[3]),
        .O(hist_acc0_carry_i_5_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_6
       (.I0(hist_acc[2]),
        .I1(hist_value[2]),
        .O(hist_acc0_carry_i_6_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_7
       (.I0(hist_acc[1]),
        .I1(hist_value[1]),
        .O(hist_acc0_carry_i_7_n_0));
  LUT2 #(
    .INIT(4'h6)) 
    hist_acc0_carry_i_8
       (.I0(hist_acc[0]),
        .I1(hist_value[0]),
        .O(hist_acc0_carry_i_8_n_0));
  LUT4 #(
    .INIT(16'h0080)) 
    \hist_acc[31]_i_1 
       (.I0(\FSM_onehot_s_state_reg_n_0_[0] ),
        .I1(start_read),
        .I2(s_axis_tvalid),
        .I3(hist_value_0),
        .O(\hist_acc[31]_i_1_n_0 ));
  LUT4 #(
    .INIT(16'hEAAA)) 
    \hist_acc[31]_i_2 
       (.I0(hist_value_0),
        .I1(s_axis_tvalid),
        .I2(start_read),
        .I3(\FSM_onehot_s_state_reg_n_0_[0] ),
        .O(hist_acc_2));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[0] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[0]),
        .Q(hist_acc[0]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[10] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[10]),
        .Q(hist_acc[10]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[11] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[11]),
        .Q(hist_acc[11]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[12] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[12]),
        .Q(hist_acc[12]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[13] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[13]),
        .Q(hist_acc[13]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[14] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[14]),
        .Q(hist_acc[14]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[15] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[15]),
        .Q(hist_acc[15]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[16] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[16]),
        .Q(hist_acc[16]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[17] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[17]),
        .Q(hist_acc[17]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[18] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[18]),
        .Q(hist_acc[18]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[19] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[19]),
        .Q(hist_acc[19]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[1] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[1]),
        .Q(hist_acc[1]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[20] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[20]),
        .Q(hist_acc[20]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[21] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[21]),
        .Q(hist_acc[21]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[22] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[22]),
        .Q(hist_acc[22]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[23] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[23]),
        .Q(hist_acc[23]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[24] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[24]),
        .Q(hist_acc[24]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[25] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[25]),
        .Q(hist_acc[25]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[26] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[26]),
        .Q(hist_acc[26]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[27] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[27]),
        .Q(hist_acc[27]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[28] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[28]),
        .Q(hist_acc[28]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[29] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[29]),
        .Q(hist_acc[29]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[2] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[2]),
        .Q(hist_acc[2]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[30] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[30]),
        .Q(hist_acc[30]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[31] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[31]),
        .Q(hist_acc[31]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[3] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[3]),
        .Q(hist_acc[3]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[4] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[4]),
        .Q(hist_acc[4]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[5] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[5]),
        .Q(hist_acc[5]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[6] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[6]),
        .Q(hist_acc[6]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[7] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[7]),
        .Q(hist_acc[7]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[8] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[8]),
        .Q(hist_acc[8]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE #(
    .INIT(1'b0)) 
    \hist_acc_reg[9] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in3[9]),
        .Q(hist_acc[9]),
        .R(\hist_acc[31]_i_1_n_0 ));
  LUT1 #(
    .INIT(2'h1)) 
    \hist_idx[0]_i_1 
       (.I0(hist_idx[0]),
        .O(in4[0]));
  (* SOFT_HLUTNM = "soft_lutpair4" *) 
  LUT2 #(
    .INIT(4'h6)) 
    \hist_idx[1]_i_1 
       (.I0(hist_idx[0]),
        .I1(hist_idx[1]),
        .O(in4[1]));
  (* SOFT_HLUTNM = "soft_lutpair4" *) 
  LUT3 #(
    .INIT(8'h78)) 
    \hist_idx[2]_i_1 
       (.I0(hist_idx[0]),
        .I1(hist_idx[1]),
        .I2(hist_idx[2]),
        .O(in4[2]));
  (* SOFT_HLUTNM = "soft_lutpair0" *) 
  LUT4 #(
    .INIT(16'h7F80)) 
    \hist_idx[3]_i_1 
       (.I0(hist_idx[1]),
        .I1(hist_idx[0]),
        .I2(hist_idx[2]),
        .I3(hist_idx[3]),
        .O(in4[3]));
  (* SOFT_HLUTNM = "soft_lutpair0" *) 
  LUT5 #(
    .INIT(32'h7FFF8000)) 
    \hist_idx[4]_i_1 
       (.I0(hist_idx[2]),
        .I1(hist_idx[0]),
        .I2(hist_idx[1]),
        .I3(hist_idx[3]),
        .I4(hist_idx[4]),
        .O(in4[4]));
  LUT6 #(
    .INIT(64'h7FFFFFFF80000000)) 
    \hist_idx[5]_i_1 
       (.I0(hist_idx[3]),
        .I1(hist_idx[1]),
        .I2(hist_idx[0]),
        .I3(hist_idx[2]),
        .I4(hist_idx[4]),
        .I5(hist_idx[5]),
        .O(in4[5]));
  (* SOFT_HLUTNM = "soft_lutpair3" *) 
  LUT2 #(
    .INIT(4'h6)) 
    \hist_idx[6]_i_1 
       (.I0(\hist_idx[7]_i_2_n_0 ),
        .I1(hist_idx[6]),
        .O(in4[6]));
  (* SOFT_HLUTNM = "soft_lutpair3" *) 
  LUT3 #(
    .INIT(8'h78)) 
    \hist_idx[7]_i_1 
       (.I0(\hist_idx[7]_i_2_n_0 ),
        .I1(hist_idx[6]),
        .I2(hist_idx[7]),
        .O(in4[7]));
  LUT6 #(
    .INIT(64'h8000000000000000)) 
    \hist_idx[7]_i_2 
       (.I0(hist_idx[5]),
        .I1(hist_idx[3]),
        .I2(hist_idx[1]),
        .I3(hist_idx[0]),
        .I4(hist_idx[2]),
        .I5(hist_idx[4]),
        .O(\hist_idx[7]_i_2_n_0 ));
  FDRE \hist_idx_reg[0] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[0]),
        .Q(hist_idx[0]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE \hist_idx_reg[1] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[1]),
        .Q(hist_idx[1]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE \hist_idx_reg[2] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[2]),
        .Q(hist_idx[2]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE \hist_idx_reg[3] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[3]),
        .Q(hist_idx[3]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE \hist_idx_reg[4] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[4]),
        .Q(hist_idx[4]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE \hist_idx_reg[5] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[5]),
        .Q(hist_idx[5]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE \hist_idx_reg[6] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[6]),
        .Q(hist_idx[6]),
        .R(\hist_acc[31]_i_1_n_0 ));
  FDRE \hist_idx_reg[7] 
       (.C(s_axis_clk),
        .CE(hist_acc_2),
        .D(in4[7]),
        .Q(hist_idx[7]),
        .R(\hist_acc[31]_i_1_n_0 ));
  LUT3 #(
    .INIT(8'hA8)) 
    \hist_median[7]_i_1 
       (.I0(hist_value_0),
        .I1(s_state1_carry__0_n_0),
        .I2(s_axis_tlast),
        .O(hist_median_1));
  FDRE \hist_median_reg[0] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[0]),
        .Q(hist_median[0]),
        .R(1'b0));
  FDRE \hist_median_reg[1] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[1]),
        .Q(hist_median[1]),
        .R(1'b0));
  FDRE \hist_median_reg[2] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[2]),
        .Q(hist_median[2]),
        .R(1'b0));
  FDRE \hist_median_reg[3] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[3]),
        .Q(hist_median[3]),
        .R(1'b0));
  FDRE \hist_median_reg[4] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[4]),
        .Q(hist_median[4]),
        .R(1'b0));
  FDRE \hist_median_reg[5] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[5]),
        .Q(hist_median[5]),
        .R(1'b0));
  FDRE \hist_median_reg[6] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[6]),
        .Q(hist_median[6]),
        .R(1'b0));
  FDRE \hist_median_reg[7] 
       (.C(s_axis_clk),
        .CE(hist_median_1),
        .D(hist_idx[7]),
        .Q(hist_median[7]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[0] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[0]),
        .Q(hist_value[0]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[10] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[10]),
        .Q(hist_value[10]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[11] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[11]),
        .Q(hist_value[11]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[12] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[12]),
        .Q(hist_value[12]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[13] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[13]),
        .Q(hist_value[13]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[14] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[14]),
        .Q(hist_value[14]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[15] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[15]),
        .Q(hist_value[15]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[16] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[16]),
        .Q(hist_value[16]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[17] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[17]),
        .Q(hist_value[17]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[18] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[18]),
        .Q(hist_value[18]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[19] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[19]),
        .Q(hist_value[19]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[1] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[1]),
        .Q(hist_value[1]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[20] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[20]),
        .Q(hist_value[20]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[21] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[21]),
        .Q(hist_value[21]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[22] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[22]),
        .Q(hist_value[22]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[23] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[23]),
        .Q(hist_value[23]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[24] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[24]),
        .Q(hist_value[24]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[25] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[25]),
        .Q(hist_value[25]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[26] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[26]),
        .Q(hist_value[26]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[27] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[27]),
        .Q(hist_value[27]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[28] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[28]),
        .Q(hist_value[28]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[29] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[29]),
        .Q(hist_value[29]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[2] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[2]),
        .Q(hist_value[2]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[30] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[30]),
        .Q(hist_value[30]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[31] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[31]),
        .Q(hist_value[31]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[3] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[3]),
        .Q(hist_value[3]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[4] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[4]),
        .Q(hist_value[4]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[5] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[5]),
        .Q(hist_value[5]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[6] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[6]),
        .Q(hist_value[6]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[7] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[7]),
        .Q(hist_value[7]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[8] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[8]),
        .Q(hist_value[8]),
        .R(1'b0));
  FDRE #(
    .INIT(1'b0)) 
    \hist_value_reg[9] 
       (.C(s_axis_clk),
        .CE(hist_value_0),
        .D(s_axis_tdata[9]),
        .Q(hist_value[9]),
        .R(1'b0));
  LUT3 #(
    .INIT(8'hB8)) 
    m_axis_tvalid_i_1
       (.I0(m_state_reg_n_0),
        .I1(m_axis_tready),
        .I2(m_axis_tlast),
        .O(m_axis_tvalid_i_1_n_0));
  FDRE m_axis_tvalid_reg
       (.C(m_axis_clk),
        .CE(1'b1),
        .D(m_axis_tvalid_i_1_n_0),
        .Q(m_axis_tlast),
        .R(1'b0));
  (* SOFT_HLUTNM = "soft_lutpair2" *) 
  LUT3 #(
    .INIT(8'h58)) 
    m_state_i_1
       (.I0(m_axis_tready),
        .I1(start_write_reg_n_0),
        .I2(m_state_reg_n_0),
        .O(m_state_i_1_n_0));
  FDRE #(
    .INIT(1'b0)) 
    m_state_reg
       (.C(m_axis_clk),
        .CE(1'b1),
        .D(m_state_i_1_n_0),
        .Q(m_state_reg_n_0),
        .R(1'b0));
  LUT4 #(
    .INIT(16'h8F80)) 
    s_axis_tready_i_1
       (.I0(s_axis_tvalid),
        .I1(start_read),
        .I2(\FSM_onehot_s_state_reg_n_0_[0] ),
        .I3(s_axis_tready),
        .O(s_axis_tready_i_1_n_0));
  FDRE s_axis_tready_reg
       (.C(s_axis_clk),
        .CE(1'b1),
        .D(s_axis_tready_i_1_n_0),
        .Q(s_axis_tready),
        .R(1'b0));
  (* COMPARATOR_THRESHOLD = "11" *) 
  CARRY8 s_state1_carry
       (.CI(1'b1),
        .CI_TOP(1'b0),
        .CO({s_state1_carry_n_0,s_state1_carry_n_1,s_state1_carry_n_2,s_state1_carry_n_3,s_state1_carry_n_4,s_state1_carry_n_5,s_state1_carry_n_6,s_state1_carry_n_7}),
        .DI({s_state1_carry_i_1_n_0,s_state1_carry_i_2_n_0,s_state1_carry_i_3_n_0,s_state1_carry_i_4_n_0,s_state1_carry_i_5_n_0,s_state1_carry_i_6_n_0,s_state1_carry_i_7_n_0,s_state1_carry_i_8_n_0}),
        .O(NLW_s_state1_carry_O_UNCONNECTED[7:0]),
        .S({s_state1_carry_i_9_n_0,s_state1_carry_i_10_n_0,s_state1_carry_i_11_n_0,s_state1_carry_i_12_n_0,s_state1_carry_i_13_n_0,s_state1_carry_i_14_n_0,s_state1_carry_i_15_n_0,s_state1_carry_i_16_n_0}));
  (* COMPARATOR_THRESHOLD = "11" *) 
  CARRY8 s_state1_carry__0
       (.CI(s_state1_carry_n_0),
        .CI_TOP(1'b0),
        .CO({s_state1_carry__0_n_0,s_state1_carry__0_n_1,s_state1_carry__0_n_2,s_state1_carry__0_n_3,s_state1_carry__0_n_4,s_state1_carry__0_n_5,s_state1_carry__0_n_6,s_state1_carry__0_n_7}),
        .DI({s_state1_carry__0_i_1_n_0,s_state1_carry__0_i_2_n_0,s_state1_carry__0_i_3_n_0,s_state1_carry__0_i_4_n_0,s_state1_carry__0_i_5_n_0,s_state1_carry__0_i_6_n_0,s_state1_carry__0_i_7_n_0,s_state1_carry__0_i_8_n_0}),
        .O(NLW_s_state1_carry__0_O_UNCONNECTED[7:0]),
        .S({s_state1_carry__0_i_9_n_0,s_state1_carry__0_i_10_n_0,s_state1_carry__0_i_11_n_0,s_state1_carry__0_i_12_n_0,s_state1_carry__0_i_13_n_0,s_state1_carry__0_i_14_n_0,s_state1_carry__0_i_15_n_0,s_state1_carry__0_i_16_n_0}));
  LUT2 #(
    .INIT(4'h2)) 
    s_state1_carry__0_i_1
       (.I0(hist_acc[30]),
        .I1(hist_acc[31]),
        .O(s_state1_carry__0_i_1_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_10
       (.I0(hist_acc[28]),
        .I1(hist_acc[29]),
        .O(s_state1_carry__0_i_10_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_11
       (.I0(hist_acc[26]),
        .I1(hist_acc[27]),
        .O(s_state1_carry__0_i_11_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_12
       (.I0(hist_acc[24]),
        .I1(hist_acc[25]),
        .O(s_state1_carry__0_i_12_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_13
       (.I0(hist_acc[22]),
        .I1(hist_acc[23]),
        .O(s_state1_carry__0_i_13_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_14
       (.I0(hist_acc[20]),
        .I1(hist_acc[21]),
        .O(s_state1_carry__0_i_14_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_15
       (.I0(hist_acc[18]),
        .I1(hist_acc[19]),
        .O(s_state1_carry__0_i_15_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_16
       (.I0(hist_acc[16]),
        .I1(hist_acc[17]),
        .O(s_state1_carry__0_i_16_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry__0_i_2
       (.I0(hist_acc[28]),
        .I1(hist_acc[29]),
        .O(s_state1_carry__0_i_2_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry__0_i_3
       (.I0(hist_acc[26]),
        .I1(hist_acc[27]),
        .O(s_state1_carry__0_i_3_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry__0_i_4
       (.I0(hist_acc[24]),
        .I1(hist_acc[25]),
        .O(s_state1_carry__0_i_4_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry__0_i_5
       (.I0(hist_acc[22]),
        .I1(hist_acc[23]),
        .O(s_state1_carry__0_i_5_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry__0_i_6
       (.I0(hist_acc[20]),
        .I1(hist_acc[21]),
        .O(s_state1_carry__0_i_6_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry__0_i_7
       (.I0(hist_acc[18]),
        .I1(hist_acc[19]),
        .O(s_state1_carry__0_i_7_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry__0_i_8
       (.I0(hist_acc[16]),
        .I1(hist_acc[17]),
        .O(s_state1_carry__0_i_8_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry__0_i_9
       (.I0(hist_acc[30]),
        .I1(hist_acc[31]),
        .O(s_state1_carry__0_i_9_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_1
       (.I0(hist_acc[14]),
        .I1(hist_acc[15]),
        .O(s_state1_carry_i_1_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_10
       (.I0(hist_acc[12]),
        .I1(hist_acc[13]),
        .O(s_state1_carry_i_10_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_11
       (.I0(hist_acc[10]),
        .I1(hist_acc[11]),
        .O(s_state1_carry_i_11_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_12
       (.I0(hist_acc[8]),
        .I1(hist_acc[9]),
        .O(s_state1_carry_i_12_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_13
       (.I0(hist_acc[6]),
        .I1(hist_acc[7]),
        .O(s_state1_carry_i_13_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_14
       (.I0(hist_acc[4]),
        .I1(hist_acc[5]),
        .O(s_state1_carry_i_14_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_15
       (.I0(hist_acc[2]),
        .I1(hist_acc[3]),
        .O(s_state1_carry_i_15_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_16
       (.I0(hist_acc[0]),
        .I1(hist_acc[1]),
        .O(s_state1_carry_i_16_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_2
       (.I0(hist_acc[12]),
        .I1(hist_acc[13]),
        .O(s_state1_carry_i_2_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_3
       (.I0(hist_acc[10]),
        .I1(hist_acc[11]),
        .O(s_state1_carry_i_3_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_4
       (.I0(hist_acc[8]),
        .I1(hist_acc[9]),
        .O(s_state1_carry_i_4_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_5
       (.I0(hist_acc[6]),
        .I1(hist_acc[7]),
        .O(s_state1_carry_i_5_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_6
       (.I0(hist_acc[4]),
        .I1(hist_acc[5]),
        .O(s_state1_carry_i_6_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_7
       (.I0(hist_acc[2]),
        .I1(hist_acc[3]),
        .O(s_state1_carry_i_7_n_0));
  LUT2 #(
    .INIT(4'hE)) 
    s_state1_carry_i_8
       (.I0(hist_acc[0]),
        .I1(hist_acc[1]),
        .O(s_state1_carry_i_8_n_0));
  LUT2 #(
    .INIT(4'h1)) 
    s_state1_carry_i_9
       (.I0(hist_acc[14]),
        .I1(hist_acc[15]),
        .O(s_state1_carry_i_9_n_0));
  (* SOFT_HLUTNM = "soft_lutpair2" *) 
  LUT4 #(
    .INIT(16'hF2AA)) 
    start_read_i_1
       (.I0(start_read),
        .I1(start_write_reg_n_0),
        .I2(m_state_reg_n_0),
        .I3(m_axis_tready),
        .O(start_read_i_1_n_0));
  FDRE #(
    .INIT(1'b1)) 
    start_read_reg
       (.C(m_axis_clk),
        .CE(1'b1),
        .D(start_read_i_1_n_0),
        .Q(start_read),
        .R(1'b0));
  (* SOFT_HLUTNM = "soft_lutpair1" *) 
  LUT5 #(
    .INIT(32'hBFFFAAAA)) 
    start_write_i_1
       (.I0(\FSM_onehot_s_state_reg_n_0_[2] ),
        .I1(s_axis_tvalid),
        .I2(start_read),
        .I3(\FSM_onehot_s_state_reg_n_0_[0] ),
        .I4(start_write_reg_n_0),
        .O(start_write_i_1_n_0));
  FDRE #(
    .INIT(1'b0)) 
    start_write_reg
       (.C(s_axis_clk),
        .CE(1'b1),
        .D(start_write_i_1_n_0),
        .Q(start_write_reg_n_0),
        .R(1'b0));
endmodule
`ifndef GLBL
`define GLBL
`timescale  1 ps / 1 ps

module glbl ();

    parameter ROC_WIDTH = 100000;
    parameter TOC_WIDTH = 0;
    parameter GRES_WIDTH = 10000;
    parameter GRES_START = 10000;

//--------   STARTUP Globals --------------
    wire GSR;
    wire GTS;
    wire GWE;
    wire PRLD;
    wire GRESTORE;
    tri1 p_up_tmp;
    tri (weak1, strong0) PLL_LOCKG = p_up_tmp;

    wire PROGB_GLBL;
    wire CCLKO_GLBL;
    wire FCSBO_GLBL;
    wire [3:0] DO_GLBL;
    wire [3:0] DI_GLBL;
   
    reg GSR_int;
    reg GTS_int;
    reg PRLD_int;
    reg GRESTORE_int;

//--------   JTAG Globals --------------
    wire JTAG_TDO_GLBL;
    wire JTAG_TCK_GLBL;
    wire JTAG_TDI_GLBL;
    wire JTAG_TMS_GLBL;
    wire JTAG_TRST_GLBL;

    reg JTAG_CAPTURE_GLBL;
    reg JTAG_RESET_GLBL;
    reg JTAG_SHIFT_GLBL;
    reg JTAG_UPDATE_GLBL;
    reg JTAG_RUNTEST_GLBL;

    reg JTAG_SEL1_GLBL = 0;
    reg JTAG_SEL2_GLBL = 0 ;
    reg JTAG_SEL3_GLBL = 0;
    reg JTAG_SEL4_GLBL = 0;

    reg JTAG_USER_TDO1_GLBL = 1'bz;
    reg JTAG_USER_TDO2_GLBL = 1'bz;
    reg JTAG_USER_TDO3_GLBL = 1'bz;
    reg JTAG_USER_TDO4_GLBL = 1'bz;

    assign (strong1, weak0) GSR = GSR_int;
    assign (strong1, weak0) GTS = GTS_int;
    assign (weak1, weak0) PRLD = PRLD_int;
    assign (strong1, weak0) GRESTORE = GRESTORE_int;

    initial begin
	GSR_int = 1'b1;
	PRLD_int = 1'b1;
	#(ROC_WIDTH)
	GSR_int = 1'b0;
	PRLD_int = 1'b0;
    end

    initial begin
	GTS_int = 1'b1;
	#(TOC_WIDTH)
	GTS_int = 1'b0;
    end

    initial begin 
	GRESTORE_int = 1'b0;
	#(GRES_START);
	GRESTORE_int = 1'b1;
	#(GRES_WIDTH);
	GRESTORE_int = 1'b0;
    end

endmodule
`endif
