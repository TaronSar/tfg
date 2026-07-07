-- Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
-- --------------------------------------------------------------------------------
-- Tool Version: Vivado v.2020.1 (lin64) Build 2902540 Wed May 27 19:54:35 MDT 2020
-- Date        : Thu Jun 20 09:13:26 2024
-- Host        : user-VirtualBox running 64-bit Ubuntu 18.04.6 LTS
-- Command     : write_vhdl -force -mode funcsim
--               /home/vmm6/projects_shared/Vision/repo/DAA/items/fpga_orb/code/test/histogram/source/bd/ip/design_1_fpga_median_top_0_0/design_1_fpga_median_top_0_0_sim_netlist.vhdl
-- Design      : design_1_fpga_median_top_0_0
-- Purpose     : This VHDL netlist is a functional simulation representation of the design and should not be modified or
--               synthesized. This netlist cannot be used for SDF annotated simulation.
-- Device      : xczu15eg-ffvb1156-2-i
-- --------------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
library UNISIM;
use UNISIM.VCOMPONENTS.ALL;
entity design_1_fpga_median_top_0_0_fpga_median_top is
  port (
    m_axis_tdata : out STD_LOGIC_VECTOR ( 7 downto 0 );
    s_axis_tready : out STD_LOGIC;
    m_axis_tlast : out STD_LOGIC;
    s_axis_tvalid : in STD_LOGIC;
    s_axis_clk : in STD_LOGIC;
    s_axis_tdata : in STD_LOGIC_VECTOR ( 31 downto 0 );
    m_axis_clk : in STD_LOGIC;
    s_axis_tlast : in STD_LOGIC;
    m_axis_tready : in STD_LOGIC
  );
  attribute ORIG_REF_NAME : string;
  attribute ORIG_REF_NAME of design_1_fpga_median_top_0_0_fpga_median_top : entity is "fpga_median_top";
end design_1_fpga_median_top_0_0_fpga_median_top;

architecture STRUCTURE of design_1_fpga_median_top_0_0_fpga_median_top is
  signal \FSM_onehot_s_state[2]_i_1_n_0\ : STD_LOGIC;
  signal \FSM_onehot_s_state[2]_i_2_n_0\ : STD_LOGIC;
  signal \FSM_onehot_s_state_reg_n_0_[0]\ : STD_LOGIC;
  signal \FSM_onehot_s_state_reg_n_0_[2]\ : STD_LOGIC;
  signal data0 : STD_LOGIC;
  signal hist_acc : STD_LOGIC_VECTOR ( 31 downto 0 );
  signal \hist_acc0_carry__0_i_1_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_i_2_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_i_3_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_i_4_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_i_5_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_i_6_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_i_7_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_i_8_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_1\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_2\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_3\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_4\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_5\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_6\ : STD_LOGIC;
  signal \hist_acc0_carry__0_n_7\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_1_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_2_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_3_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_4_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_5_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_6_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_7_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_i_8_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_1\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_2\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_3\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_4\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_5\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_6\ : STD_LOGIC;
  signal \hist_acc0_carry__1_n_7\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_1_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_2_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_3_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_4_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_5_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_6_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_7_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_i_8_n_0\ : STD_LOGIC;
  signal \hist_acc0_carry__2_n_1\ : STD_LOGIC;
  signal \hist_acc0_carry__2_n_2\ : STD_LOGIC;
  signal \hist_acc0_carry__2_n_3\ : STD_LOGIC;
  signal \hist_acc0_carry__2_n_4\ : STD_LOGIC;
  signal \hist_acc0_carry__2_n_5\ : STD_LOGIC;
  signal \hist_acc0_carry__2_n_6\ : STD_LOGIC;
  signal \hist_acc0_carry__2_n_7\ : STD_LOGIC;
  signal hist_acc0_carry_i_1_n_0 : STD_LOGIC;
  signal hist_acc0_carry_i_2_n_0 : STD_LOGIC;
  signal hist_acc0_carry_i_3_n_0 : STD_LOGIC;
  signal hist_acc0_carry_i_4_n_0 : STD_LOGIC;
  signal hist_acc0_carry_i_5_n_0 : STD_LOGIC;
  signal hist_acc0_carry_i_6_n_0 : STD_LOGIC;
  signal hist_acc0_carry_i_7_n_0 : STD_LOGIC;
  signal hist_acc0_carry_i_8_n_0 : STD_LOGIC;
  signal hist_acc0_carry_n_0 : STD_LOGIC;
  signal hist_acc0_carry_n_1 : STD_LOGIC;
  signal hist_acc0_carry_n_2 : STD_LOGIC;
  signal hist_acc0_carry_n_3 : STD_LOGIC;
  signal hist_acc0_carry_n_4 : STD_LOGIC;
  signal hist_acc0_carry_n_5 : STD_LOGIC;
  signal hist_acc0_carry_n_6 : STD_LOGIC;
  signal hist_acc0_carry_n_7 : STD_LOGIC;
  signal \hist_acc[31]_i_1_n_0\ : STD_LOGIC;
  signal hist_acc_2 : STD_LOGIC;
  signal hist_idx : STD_LOGIC_VECTOR ( 7 downto 0 );
  signal \hist_idx[7]_i_2_n_0\ : STD_LOGIC;
  signal hist_median : STD_LOGIC_VECTOR ( 7 downto 0 );
  signal hist_median_1 : STD_LOGIC;
  signal hist_value : STD_LOGIC_VECTOR ( 31 downto 0 );
  signal hist_value_0 : STD_LOGIC;
  signal in3 : STD_LOGIC_VECTOR ( 31 downto 0 );
  signal in4 : STD_LOGIC_VECTOR ( 7 downto 0 );
  signal \^m_axis_tlast\ : STD_LOGIC;
  signal m_axis_tvalid_i_1_n_0 : STD_LOGIC;
  signal m_state_i_1_n_0 : STD_LOGIC;
  signal m_state_reg_n_0 : STD_LOGIC;
  signal \^s_axis_tready\ : STD_LOGIC;
  signal s_axis_tready_i_1_n_0 : STD_LOGIC;
  signal \s_state1_carry__0_i_10_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_11_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_12_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_13_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_14_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_15_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_16_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_1_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_2_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_3_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_4_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_5_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_6_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_7_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_8_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_i_9_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_n_0\ : STD_LOGIC;
  signal \s_state1_carry__0_n_1\ : STD_LOGIC;
  signal \s_state1_carry__0_n_2\ : STD_LOGIC;
  signal \s_state1_carry__0_n_3\ : STD_LOGIC;
  signal \s_state1_carry__0_n_4\ : STD_LOGIC;
  signal \s_state1_carry__0_n_5\ : STD_LOGIC;
  signal \s_state1_carry__0_n_6\ : STD_LOGIC;
  signal \s_state1_carry__0_n_7\ : STD_LOGIC;
  signal s_state1_carry_i_10_n_0 : STD_LOGIC;
  signal s_state1_carry_i_11_n_0 : STD_LOGIC;
  signal s_state1_carry_i_12_n_0 : STD_LOGIC;
  signal s_state1_carry_i_13_n_0 : STD_LOGIC;
  signal s_state1_carry_i_14_n_0 : STD_LOGIC;
  signal s_state1_carry_i_15_n_0 : STD_LOGIC;
  signal s_state1_carry_i_16_n_0 : STD_LOGIC;
  signal s_state1_carry_i_1_n_0 : STD_LOGIC;
  signal s_state1_carry_i_2_n_0 : STD_LOGIC;
  signal s_state1_carry_i_3_n_0 : STD_LOGIC;
  signal s_state1_carry_i_4_n_0 : STD_LOGIC;
  signal s_state1_carry_i_5_n_0 : STD_LOGIC;
  signal s_state1_carry_i_6_n_0 : STD_LOGIC;
  signal s_state1_carry_i_7_n_0 : STD_LOGIC;
  signal s_state1_carry_i_8_n_0 : STD_LOGIC;
  signal s_state1_carry_i_9_n_0 : STD_LOGIC;
  signal s_state1_carry_n_0 : STD_LOGIC;
  signal s_state1_carry_n_1 : STD_LOGIC;
  signal s_state1_carry_n_2 : STD_LOGIC;
  signal s_state1_carry_n_3 : STD_LOGIC;
  signal s_state1_carry_n_4 : STD_LOGIC;
  signal s_state1_carry_n_5 : STD_LOGIC;
  signal s_state1_carry_n_6 : STD_LOGIC;
  signal s_state1_carry_n_7 : STD_LOGIC;
  signal start_read : STD_LOGIC;
  signal start_read_i_1_n_0 : STD_LOGIC;
  signal start_write_i_1_n_0 : STD_LOGIC;
  signal start_write_reg_n_0 : STD_LOGIC;
  signal \NLW_hist_acc0_carry__2_CO_UNCONNECTED\ : STD_LOGIC_VECTOR ( 7 to 7 );
  signal NLW_s_state1_carry_O_UNCONNECTED : STD_LOGIC_VECTOR ( 7 downto 0 );
  signal \NLW_s_state1_carry__0_O_UNCONNECTED\ : STD_LOGIC_VECTOR ( 7 downto 0 );
  attribute SOFT_HLUTNM : string;
  attribute SOFT_HLUTNM of \FSM_onehot_s_state[2]_i_2\ : label is "soft_lutpair1";
  attribute FSM_ENCODED_STATES : string;
  attribute FSM_ENCODED_STATES of \FSM_onehot_s_state_reg[0]\ : label is "idle:001,calc:010,save:100,";
  attribute FSM_ENCODED_STATES of \FSM_onehot_s_state_reg[1]\ : label is "idle:001,calc:010,save:100,";
  attribute FSM_ENCODED_STATES of \FSM_onehot_s_state_reg[2]\ : label is "idle:001,calc:010,save:100,";
  attribute ADDER_THRESHOLD : integer;
  attribute ADDER_THRESHOLD of hist_acc0_carry : label is 35;
  attribute ADDER_THRESHOLD of \hist_acc0_carry__0\ : label is 35;
  attribute ADDER_THRESHOLD of \hist_acc0_carry__1\ : label is 35;
  attribute ADDER_THRESHOLD of \hist_acc0_carry__2\ : label is 35;
  attribute SOFT_HLUTNM of \hist_idx[1]_i_1\ : label is "soft_lutpair4";
  attribute SOFT_HLUTNM of \hist_idx[2]_i_1\ : label is "soft_lutpair4";
  attribute SOFT_HLUTNM of \hist_idx[3]_i_1\ : label is "soft_lutpair0";
  attribute SOFT_HLUTNM of \hist_idx[4]_i_1\ : label is "soft_lutpair0";
  attribute SOFT_HLUTNM of \hist_idx[6]_i_1\ : label is "soft_lutpair3";
  attribute SOFT_HLUTNM of \hist_idx[7]_i_1\ : label is "soft_lutpair3";
  attribute SOFT_HLUTNM of m_state_i_1 : label is "soft_lutpair2";
  attribute COMPARATOR_THRESHOLD : integer;
  attribute COMPARATOR_THRESHOLD of s_state1_carry : label is 11;
  attribute COMPARATOR_THRESHOLD of \s_state1_carry__0\ : label is 11;
  attribute SOFT_HLUTNM of start_read_i_1 : label is "soft_lutpair2";
  attribute SOFT_HLUTNM of start_write_i_1 : label is "soft_lutpair1";
begin
  m_axis_tlast <= \^m_axis_tlast\;
  s_axis_tready <= \^s_axis_tready\;
\FSM_onehot_s_state[2]_i_1\: unisim.vcomponents.LUT5
    generic map(
      INIT => X"FEFEFEEE"
    )
        port map (
      I0 => \FSM_onehot_s_state_reg_n_0_[2]\,
      I1 => \FSM_onehot_s_state[2]_i_2_n_0\,
      I2 => hist_value_0,
      I3 => \s_state1_carry__0_n_0\,
      I4 => s_axis_tlast,
      O => \FSM_onehot_s_state[2]_i_1_n_0\
    );
\FSM_onehot_s_state[2]_i_2\: unisim.vcomponents.LUT3
    generic map(
      INIT => X"80"
    )
        port map (
      I0 => \FSM_onehot_s_state_reg_n_0_[0]\,
      I1 => start_read,
      I2 => s_axis_tvalid,
      O => \FSM_onehot_s_state[2]_i_2_n_0\
    );
\FSM_onehot_s_state_reg[0]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '1'
    )
        port map (
      C => s_axis_clk,
      CE => \FSM_onehot_s_state[2]_i_1_n_0\,
      D => \FSM_onehot_s_state_reg_n_0_[2]\,
      Q => \FSM_onehot_s_state_reg_n_0_[0]\,
      R => '0'
    );
\FSM_onehot_s_state_reg[1]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => \FSM_onehot_s_state[2]_i_1_n_0\,
      D => \FSM_onehot_s_state_reg_n_0_[0]\,
      Q => hist_value_0,
      R => '0'
    );
\FSM_onehot_s_state_reg[2]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => \FSM_onehot_s_state[2]_i_1_n_0\,
      D => hist_value_0,
      Q => \FSM_onehot_s_state_reg_n_0_[2]\,
      R => '0'
    );
\data[7]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"8"
    )
        port map (
      I0 => m_axis_tready,
      I1 => m_state_reg_n_0,
      O => data0
    );
\data_reg[0]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(0),
      Q => m_axis_tdata(0),
      R => '0'
    );
\data_reg[1]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(1),
      Q => m_axis_tdata(1),
      R => '0'
    );
\data_reg[2]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(2),
      Q => m_axis_tdata(2),
      R => '0'
    );
\data_reg[3]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(3),
      Q => m_axis_tdata(3),
      R => '0'
    );
\data_reg[4]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(4),
      Q => m_axis_tdata(4),
      R => '0'
    );
\data_reg[5]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(5),
      Q => m_axis_tdata(5),
      R => '0'
    );
\data_reg[6]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(6),
      Q => m_axis_tdata(6),
      R => '0'
    );
\data_reg[7]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => data0,
      D => hist_median(7),
      Q => m_axis_tdata(7),
      R => '0'
    );
hist_acc0_carry: unisim.vcomponents.CARRY8
     port map (
      CI => '0',
      CI_TOP => '0',
      CO(7) => hist_acc0_carry_n_0,
      CO(6) => hist_acc0_carry_n_1,
      CO(5) => hist_acc0_carry_n_2,
      CO(4) => hist_acc0_carry_n_3,
      CO(3) => hist_acc0_carry_n_4,
      CO(2) => hist_acc0_carry_n_5,
      CO(1) => hist_acc0_carry_n_6,
      CO(0) => hist_acc0_carry_n_7,
      DI(7 downto 0) => hist_acc(7 downto 0),
      O(7 downto 0) => in3(7 downto 0),
      S(7) => hist_acc0_carry_i_1_n_0,
      S(6) => hist_acc0_carry_i_2_n_0,
      S(5) => hist_acc0_carry_i_3_n_0,
      S(4) => hist_acc0_carry_i_4_n_0,
      S(3) => hist_acc0_carry_i_5_n_0,
      S(2) => hist_acc0_carry_i_6_n_0,
      S(1) => hist_acc0_carry_i_7_n_0,
      S(0) => hist_acc0_carry_i_8_n_0
    );
\hist_acc0_carry__0\: unisim.vcomponents.CARRY8
     port map (
      CI => hist_acc0_carry_n_0,
      CI_TOP => '0',
      CO(7) => \hist_acc0_carry__0_n_0\,
      CO(6) => \hist_acc0_carry__0_n_1\,
      CO(5) => \hist_acc0_carry__0_n_2\,
      CO(4) => \hist_acc0_carry__0_n_3\,
      CO(3) => \hist_acc0_carry__0_n_4\,
      CO(2) => \hist_acc0_carry__0_n_5\,
      CO(1) => \hist_acc0_carry__0_n_6\,
      CO(0) => \hist_acc0_carry__0_n_7\,
      DI(7 downto 0) => hist_acc(15 downto 8),
      O(7 downto 0) => in3(15 downto 8),
      S(7) => \hist_acc0_carry__0_i_1_n_0\,
      S(6) => \hist_acc0_carry__0_i_2_n_0\,
      S(5) => \hist_acc0_carry__0_i_3_n_0\,
      S(4) => \hist_acc0_carry__0_i_4_n_0\,
      S(3) => \hist_acc0_carry__0_i_5_n_0\,
      S(2) => \hist_acc0_carry__0_i_6_n_0\,
      S(1) => \hist_acc0_carry__0_i_7_n_0\,
      S(0) => \hist_acc0_carry__0_i_8_n_0\
    );
\hist_acc0_carry__0_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(15),
      I1 => hist_value(15),
      O => \hist_acc0_carry__0_i_1_n_0\
    );
\hist_acc0_carry__0_i_2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(14),
      I1 => hist_value(14),
      O => \hist_acc0_carry__0_i_2_n_0\
    );
\hist_acc0_carry__0_i_3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(13),
      I1 => hist_value(13),
      O => \hist_acc0_carry__0_i_3_n_0\
    );
\hist_acc0_carry__0_i_4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(12),
      I1 => hist_value(12),
      O => \hist_acc0_carry__0_i_4_n_0\
    );
\hist_acc0_carry__0_i_5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(11),
      I1 => hist_value(11),
      O => \hist_acc0_carry__0_i_5_n_0\
    );
\hist_acc0_carry__0_i_6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(10),
      I1 => hist_value(10),
      O => \hist_acc0_carry__0_i_6_n_0\
    );
\hist_acc0_carry__0_i_7\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(9),
      I1 => hist_value(9),
      O => \hist_acc0_carry__0_i_7_n_0\
    );
\hist_acc0_carry__0_i_8\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(8),
      I1 => hist_value(8),
      O => \hist_acc0_carry__0_i_8_n_0\
    );
\hist_acc0_carry__1\: unisim.vcomponents.CARRY8
     port map (
      CI => \hist_acc0_carry__0_n_0\,
      CI_TOP => '0',
      CO(7) => \hist_acc0_carry__1_n_0\,
      CO(6) => \hist_acc0_carry__1_n_1\,
      CO(5) => \hist_acc0_carry__1_n_2\,
      CO(4) => \hist_acc0_carry__1_n_3\,
      CO(3) => \hist_acc0_carry__1_n_4\,
      CO(2) => \hist_acc0_carry__1_n_5\,
      CO(1) => \hist_acc0_carry__1_n_6\,
      CO(0) => \hist_acc0_carry__1_n_7\,
      DI(7 downto 0) => hist_acc(23 downto 16),
      O(7 downto 0) => in3(23 downto 16),
      S(7) => \hist_acc0_carry__1_i_1_n_0\,
      S(6) => \hist_acc0_carry__1_i_2_n_0\,
      S(5) => \hist_acc0_carry__1_i_3_n_0\,
      S(4) => \hist_acc0_carry__1_i_4_n_0\,
      S(3) => \hist_acc0_carry__1_i_5_n_0\,
      S(2) => \hist_acc0_carry__1_i_6_n_0\,
      S(1) => \hist_acc0_carry__1_i_7_n_0\,
      S(0) => \hist_acc0_carry__1_i_8_n_0\
    );
\hist_acc0_carry__1_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(23),
      I1 => hist_value(23),
      O => \hist_acc0_carry__1_i_1_n_0\
    );
\hist_acc0_carry__1_i_2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(22),
      I1 => hist_value(22),
      O => \hist_acc0_carry__1_i_2_n_0\
    );
\hist_acc0_carry__1_i_3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(21),
      I1 => hist_value(21),
      O => \hist_acc0_carry__1_i_3_n_0\
    );
\hist_acc0_carry__1_i_4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(20),
      I1 => hist_value(20),
      O => \hist_acc0_carry__1_i_4_n_0\
    );
\hist_acc0_carry__1_i_5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(19),
      I1 => hist_value(19),
      O => \hist_acc0_carry__1_i_5_n_0\
    );
\hist_acc0_carry__1_i_6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(18),
      I1 => hist_value(18),
      O => \hist_acc0_carry__1_i_6_n_0\
    );
\hist_acc0_carry__1_i_7\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(17),
      I1 => hist_value(17),
      O => \hist_acc0_carry__1_i_7_n_0\
    );
\hist_acc0_carry__1_i_8\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(16),
      I1 => hist_value(16),
      O => \hist_acc0_carry__1_i_8_n_0\
    );
\hist_acc0_carry__2\: unisim.vcomponents.CARRY8
     port map (
      CI => \hist_acc0_carry__1_n_0\,
      CI_TOP => '0',
      CO(7) => \NLW_hist_acc0_carry__2_CO_UNCONNECTED\(7),
      CO(6) => \hist_acc0_carry__2_n_1\,
      CO(5) => \hist_acc0_carry__2_n_2\,
      CO(4) => \hist_acc0_carry__2_n_3\,
      CO(3) => \hist_acc0_carry__2_n_4\,
      CO(2) => \hist_acc0_carry__2_n_5\,
      CO(1) => \hist_acc0_carry__2_n_6\,
      CO(0) => \hist_acc0_carry__2_n_7\,
      DI(7) => '0',
      DI(6 downto 0) => hist_acc(30 downto 24),
      O(7 downto 0) => in3(31 downto 24),
      S(7) => \hist_acc0_carry__2_i_1_n_0\,
      S(6) => \hist_acc0_carry__2_i_2_n_0\,
      S(5) => \hist_acc0_carry__2_i_3_n_0\,
      S(4) => \hist_acc0_carry__2_i_4_n_0\,
      S(3) => \hist_acc0_carry__2_i_5_n_0\,
      S(2) => \hist_acc0_carry__2_i_6_n_0\,
      S(1) => \hist_acc0_carry__2_i_7_n_0\,
      S(0) => \hist_acc0_carry__2_i_8_n_0\
    );
\hist_acc0_carry__2_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(31),
      I1 => hist_value(31),
      O => \hist_acc0_carry__2_i_1_n_0\
    );
\hist_acc0_carry__2_i_2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(30),
      I1 => hist_value(30),
      O => \hist_acc0_carry__2_i_2_n_0\
    );
\hist_acc0_carry__2_i_3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(29),
      I1 => hist_value(29),
      O => \hist_acc0_carry__2_i_3_n_0\
    );
\hist_acc0_carry__2_i_4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(28),
      I1 => hist_value(28),
      O => \hist_acc0_carry__2_i_4_n_0\
    );
\hist_acc0_carry__2_i_5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(27),
      I1 => hist_value(27),
      O => \hist_acc0_carry__2_i_5_n_0\
    );
\hist_acc0_carry__2_i_6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(26),
      I1 => hist_value(26),
      O => \hist_acc0_carry__2_i_6_n_0\
    );
\hist_acc0_carry__2_i_7\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(25),
      I1 => hist_value(25),
      O => \hist_acc0_carry__2_i_7_n_0\
    );
\hist_acc0_carry__2_i_8\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(24),
      I1 => hist_value(24),
      O => \hist_acc0_carry__2_i_8_n_0\
    );
hist_acc0_carry_i_1: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(7),
      I1 => hist_value(7),
      O => hist_acc0_carry_i_1_n_0
    );
hist_acc0_carry_i_2: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(6),
      I1 => hist_value(6),
      O => hist_acc0_carry_i_2_n_0
    );
hist_acc0_carry_i_3: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(5),
      I1 => hist_value(5),
      O => hist_acc0_carry_i_3_n_0
    );
hist_acc0_carry_i_4: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(4),
      I1 => hist_value(4),
      O => hist_acc0_carry_i_4_n_0
    );
hist_acc0_carry_i_5: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(3),
      I1 => hist_value(3),
      O => hist_acc0_carry_i_5_n_0
    );
hist_acc0_carry_i_6: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(2),
      I1 => hist_value(2),
      O => hist_acc0_carry_i_6_n_0
    );
hist_acc0_carry_i_7: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(1),
      I1 => hist_value(1),
      O => hist_acc0_carry_i_7_n_0
    );
hist_acc0_carry_i_8: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_acc(0),
      I1 => hist_value(0),
      O => hist_acc0_carry_i_8_n_0
    );
\hist_acc[31]_i_1\: unisim.vcomponents.LUT4
    generic map(
      INIT => X"0080"
    )
        port map (
      I0 => \FSM_onehot_s_state_reg_n_0_[0]\,
      I1 => start_read,
      I2 => s_axis_tvalid,
      I3 => hist_value_0,
      O => \hist_acc[31]_i_1_n_0\
    );
\hist_acc[31]_i_2\: unisim.vcomponents.LUT4
    generic map(
      INIT => X"EAAA"
    )
        port map (
      I0 => hist_value_0,
      I1 => s_axis_tvalid,
      I2 => start_read,
      I3 => \FSM_onehot_s_state_reg_n_0_[0]\,
      O => hist_acc_2
    );
\hist_acc_reg[0]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(0),
      Q => hist_acc(0),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[10]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(10),
      Q => hist_acc(10),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[11]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(11),
      Q => hist_acc(11),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[12]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(12),
      Q => hist_acc(12),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[13]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(13),
      Q => hist_acc(13),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[14]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(14),
      Q => hist_acc(14),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[15]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(15),
      Q => hist_acc(15),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[16]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(16),
      Q => hist_acc(16),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[17]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(17),
      Q => hist_acc(17),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[18]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(18),
      Q => hist_acc(18),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[19]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(19),
      Q => hist_acc(19),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[1]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(1),
      Q => hist_acc(1),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[20]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(20),
      Q => hist_acc(20),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[21]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(21),
      Q => hist_acc(21),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[22]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(22),
      Q => hist_acc(22),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[23]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(23),
      Q => hist_acc(23),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[24]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(24),
      Q => hist_acc(24),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[25]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(25),
      Q => hist_acc(25),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[26]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(26),
      Q => hist_acc(26),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[27]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(27),
      Q => hist_acc(27),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[28]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(28),
      Q => hist_acc(28),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[29]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(29),
      Q => hist_acc(29),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[2]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(2),
      Q => hist_acc(2),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[30]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(30),
      Q => hist_acc(30),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[31]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(31),
      Q => hist_acc(31),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[3]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(3),
      Q => hist_acc(3),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[4]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(4),
      Q => hist_acc(4),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[5]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(5),
      Q => hist_acc(5),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[6]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(6),
      Q => hist_acc(6),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[7]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(7),
      Q => hist_acc(7),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[8]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(8),
      Q => hist_acc(8),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_acc_reg[9]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in3(9),
      Q => hist_acc(9),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx[0]_i_1\: unisim.vcomponents.LUT1
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_idx(0),
      O => in4(0)
    );
\hist_idx[1]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => hist_idx(0),
      I1 => hist_idx(1),
      O => in4(1)
    );
\hist_idx[2]_i_1\: unisim.vcomponents.LUT3
    generic map(
      INIT => X"78"
    )
        port map (
      I0 => hist_idx(0),
      I1 => hist_idx(1),
      I2 => hist_idx(2),
      O => in4(2)
    );
\hist_idx[3]_i_1\: unisim.vcomponents.LUT4
    generic map(
      INIT => X"7F80"
    )
        port map (
      I0 => hist_idx(1),
      I1 => hist_idx(0),
      I2 => hist_idx(2),
      I3 => hist_idx(3),
      O => in4(3)
    );
\hist_idx[4]_i_1\: unisim.vcomponents.LUT5
    generic map(
      INIT => X"7FFF8000"
    )
        port map (
      I0 => hist_idx(2),
      I1 => hist_idx(0),
      I2 => hist_idx(1),
      I3 => hist_idx(3),
      I4 => hist_idx(4),
      O => in4(4)
    );
\hist_idx[5]_i_1\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"7FFFFFFF80000000"
    )
        port map (
      I0 => hist_idx(3),
      I1 => hist_idx(1),
      I2 => hist_idx(0),
      I3 => hist_idx(2),
      I4 => hist_idx(4),
      I5 => hist_idx(5),
      O => in4(5)
    );
\hist_idx[6]_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"6"
    )
        port map (
      I0 => \hist_idx[7]_i_2_n_0\,
      I1 => hist_idx(6),
      O => in4(6)
    );
\hist_idx[7]_i_1\: unisim.vcomponents.LUT3
    generic map(
      INIT => X"78"
    )
        port map (
      I0 => \hist_idx[7]_i_2_n_0\,
      I1 => hist_idx(6),
      I2 => hist_idx(7),
      O => in4(7)
    );
\hist_idx[7]_i_2\: unisim.vcomponents.LUT6
    generic map(
      INIT => X"8000000000000000"
    )
        port map (
      I0 => hist_idx(5),
      I1 => hist_idx(3),
      I2 => hist_idx(1),
      I3 => hist_idx(0),
      I4 => hist_idx(2),
      I5 => hist_idx(4),
      O => \hist_idx[7]_i_2_n_0\
    );
\hist_idx_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(0),
      Q => hist_idx(0),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(1),
      Q => hist_idx(1),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(2),
      Q => hist_idx(2),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(3),
      Q => hist_idx(3),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx_reg[4]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(4),
      Q => hist_idx(4),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx_reg[5]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(5),
      Q => hist_idx(5),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx_reg[6]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(6),
      Q => hist_idx(6),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_idx_reg[7]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_acc_2,
      D => in4(7),
      Q => hist_idx(7),
      R => \hist_acc[31]_i_1_n_0\
    );
\hist_median[7]_i_1\: unisim.vcomponents.LUT3
    generic map(
      INIT => X"A8"
    )
        port map (
      I0 => hist_value_0,
      I1 => \s_state1_carry__0_n_0\,
      I2 => s_axis_tlast,
      O => hist_median_1
    );
\hist_median_reg[0]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(0),
      Q => hist_median(0),
      R => '0'
    );
\hist_median_reg[1]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(1),
      Q => hist_median(1),
      R => '0'
    );
\hist_median_reg[2]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(2),
      Q => hist_median(2),
      R => '0'
    );
\hist_median_reg[3]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(3),
      Q => hist_median(3),
      R => '0'
    );
\hist_median_reg[4]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(4),
      Q => hist_median(4),
      R => '0'
    );
\hist_median_reg[5]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(5),
      Q => hist_median(5),
      R => '0'
    );
\hist_median_reg[6]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(6),
      Q => hist_median(6),
      R => '0'
    );
\hist_median_reg[7]\: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => hist_median_1,
      D => hist_idx(7),
      Q => hist_median(7),
      R => '0'
    );
\hist_value_reg[0]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(0),
      Q => hist_value(0),
      R => '0'
    );
\hist_value_reg[10]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(10),
      Q => hist_value(10),
      R => '0'
    );
\hist_value_reg[11]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(11),
      Q => hist_value(11),
      R => '0'
    );
\hist_value_reg[12]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(12),
      Q => hist_value(12),
      R => '0'
    );
\hist_value_reg[13]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(13),
      Q => hist_value(13),
      R => '0'
    );
\hist_value_reg[14]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(14),
      Q => hist_value(14),
      R => '0'
    );
\hist_value_reg[15]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(15),
      Q => hist_value(15),
      R => '0'
    );
\hist_value_reg[16]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(16),
      Q => hist_value(16),
      R => '0'
    );
\hist_value_reg[17]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(17),
      Q => hist_value(17),
      R => '0'
    );
\hist_value_reg[18]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(18),
      Q => hist_value(18),
      R => '0'
    );
\hist_value_reg[19]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(19),
      Q => hist_value(19),
      R => '0'
    );
\hist_value_reg[1]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(1),
      Q => hist_value(1),
      R => '0'
    );
\hist_value_reg[20]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(20),
      Q => hist_value(20),
      R => '0'
    );
\hist_value_reg[21]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(21),
      Q => hist_value(21),
      R => '0'
    );
\hist_value_reg[22]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(22),
      Q => hist_value(22),
      R => '0'
    );
\hist_value_reg[23]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(23),
      Q => hist_value(23),
      R => '0'
    );
\hist_value_reg[24]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(24),
      Q => hist_value(24),
      R => '0'
    );
\hist_value_reg[25]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(25),
      Q => hist_value(25),
      R => '0'
    );
\hist_value_reg[26]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(26),
      Q => hist_value(26),
      R => '0'
    );
\hist_value_reg[27]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(27),
      Q => hist_value(27),
      R => '0'
    );
\hist_value_reg[28]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(28),
      Q => hist_value(28),
      R => '0'
    );
\hist_value_reg[29]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(29),
      Q => hist_value(29),
      R => '0'
    );
\hist_value_reg[2]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(2),
      Q => hist_value(2),
      R => '0'
    );
\hist_value_reg[30]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(30),
      Q => hist_value(30),
      R => '0'
    );
\hist_value_reg[31]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(31),
      Q => hist_value(31),
      R => '0'
    );
\hist_value_reg[3]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(3),
      Q => hist_value(3),
      R => '0'
    );
\hist_value_reg[4]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(4),
      Q => hist_value(4),
      R => '0'
    );
\hist_value_reg[5]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(5),
      Q => hist_value(5),
      R => '0'
    );
\hist_value_reg[6]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(6),
      Q => hist_value(6),
      R => '0'
    );
\hist_value_reg[7]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(7),
      Q => hist_value(7),
      R => '0'
    );
\hist_value_reg[8]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(8),
      Q => hist_value(8),
      R => '0'
    );
\hist_value_reg[9]\: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => hist_value_0,
      D => s_axis_tdata(9),
      Q => hist_value(9),
      R => '0'
    );
m_axis_tvalid_i_1: unisim.vcomponents.LUT3
    generic map(
      INIT => X"B8"
    )
        port map (
      I0 => m_state_reg_n_0,
      I1 => m_axis_tready,
      I2 => \^m_axis_tlast\,
      O => m_axis_tvalid_i_1_n_0
    );
m_axis_tvalid_reg: unisim.vcomponents.FDRE
     port map (
      C => m_axis_clk,
      CE => '1',
      D => m_axis_tvalid_i_1_n_0,
      Q => \^m_axis_tlast\,
      R => '0'
    );
m_state_i_1: unisim.vcomponents.LUT3
    generic map(
      INIT => X"58"
    )
        port map (
      I0 => m_axis_tready,
      I1 => start_write_reg_n_0,
      I2 => m_state_reg_n_0,
      O => m_state_i_1_n_0
    );
m_state_reg: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => m_axis_clk,
      CE => '1',
      D => m_state_i_1_n_0,
      Q => m_state_reg_n_0,
      R => '0'
    );
s_axis_tready_i_1: unisim.vcomponents.LUT4
    generic map(
      INIT => X"8F80"
    )
        port map (
      I0 => s_axis_tvalid,
      I1 => start_read,
      I2 => \FSM_onehot_s_state_reg_n_0_[0]\,
      I3 => \^s_axis_tready\,
      O => s_axis_tready_i_1_n_0
    );
s_axis_tready_reg: unisim.vcomponents.FDRE
     port map (
      C => s_axis_clk,
      CE => '1',
      D => s_axis_tready_i_1_n_0,
      Q => \^s_axis_tready\,
      R => '0'
    );
s_state1_carry: unisim.vcomponents.CARRY8
     port map (
      CI => '1',
      CI_TOP => '0',
      CO(7) => s_state1_carry_n_0,
      CO(6) => s_state1_carry_n_1,
      CO(5) => s_state1_carry_n_2,
      CO(4) => s_state1_carry_n_3,
      CO(3) => s_state1_carry_n_4,
      CO(2) => s_state1_carry_n_5,
      CO(1) => s_state1_carry_n_6,
      CO(0) => s_state1_carry_n_7,
      DI(7) => s_state1_carry_i_1_n_0,
      DI(6) => s_state1_carry_i_2_n_0,
      DI(5) => s_state1_carry_i_3_n_0,
      DI(4) => s_state1_carry_i_4_n_0,
      DI(3) => s_state1_carry_i_5_n_0,
      DI(2) => s_state1_carry_i_6_n_0,
      DI(1) => s_state1_carry_i_7_n_0,
      DI(0) => s_state1_carry_i_8_n_0,
      O(7 downto 0) => NLW_s_state1_carry_O_UNCONNECTED(7 downto 0),
      S(7) => s_state1_carry_i_9_n_0,
      S(6) => s_state1_carry_i_10_n_0,
      S(5) => s_state1_carry_i_11_n_0,
      S(4) => s_state1_carry_i_12_n_0,
      S(3) => s_state1_carry_i_13_n_0,
      S(2) => s_state1_carry_i_14_n_0,
      S(1) => s_state1_carry_i_15_n_0,
      S(0) => s_state1_carry_i_16_n_0
    );
\s_state1_carry__0\: unisim.vcomponents.CARRY8
     port map (
      CI => s_state1_carry_n_0,
      CI_TOP => '0',
      CO(7) => \s_state1_carry__0_n_0\,
      CO(6) => \s_state1_carry__0_n_1\,
      CO(5) => \s_state1_carry__0_n_2\,
      CO(4) => \s_state1_carry__0_n_3\,
      CO(3) => \s_state1_carry__0_n_4\,
      CO(2) => \s_state1_carry__0_n_5\,
      CO(1) => \s_state1_carry__0_n_6\,
      CO(0) => \s_state1_carry__0_n_7\,
      DI(7) => \s_state1_carry__0_i_1_n_0\,
      DI(6) => \s_state1_carry__0_i_2_n_0\,
      DI(5) => \s_state1_carry__0_i_3_n_0\,
      DI(4) => \s_state1_carry__0_i_4_n_0\,
      DI(3) => \s_state1_carry__0_i_5_n_0\,
      DI(2) => \s_state1_carry__0_i_6_n_0\,
      DI(1) => \s_state1_carry__0_i_7_n_0\,
      DI(0) => \s_state1_carry__0_i_8_n_0\,
      O(7 downto 0) => \NLW_s_state1_carry__0_O_UNCONNECTED\(7 downto 0),
      S(7) => \s_state1_carry__0_i_9_n_0\,
      S(6) => \s_state1_carry__0_i_10_n_0\,
      S(5) => \s_state1_carry__0_i_11_n_0\,
      S(4) => \s_state1_carry__0_i_12_n_0\,
      S(3) => \s_state1_carry__0_i_13_n_0\,
      S(2) => \s_state1_carry__0_i_14_n_0\,
      S(1) => \s_state1_carry__0_i_15_n_0\,
      S(0) => \s_state1_carry__0_i_16_n_0\
    );
\s_state1_carry__0_i_1\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"2"
    )
        port map (
      I0 => hist_acc(30),
      I1 => hist_acc(31),
      O => \s_state1_carry__0_i_1_n_0\
    );
\s_state1_carry__0_i_10\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(28),
      I1 => hist_acc(29),
      O => \s_state1_carry__0_i_10_n_0\
    );
\s_state1_carry__0_i_11\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(26),
      I1 => hist_acc(27),
      O => \s_state1_carry__0_i_11_n_0\
    );
\s_state1_carry__0_i_12\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(24),
      I1 => hist_acc(25),
      O => \s_state1_carry__0_i_12_n_0\
    );
\s_state1_carry__0_i_13\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(22),
      I1 => hist_acc(23),
      O => \s_state1_carry__0_i_13_n_0\
    );
\s_state1_carry__0_i_14\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(20),
      I1 => hist_acc(21),
      O => \s_state1_carry__0_i_14_n_0\
    );
\s_state1_carry__0_i_15\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(18),
      I1 => hist_acc(19),
      O => \s_state1_carry__0_i_15_n_0\
    );
\s_state1_carry__0_i_16\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(16),
      I1 => hist_acc(17),
      O => \s_state1_carry__0_i_16_n_0\
    );
\s_state1_carry__0_i_2\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(28),
      I1 => hist_acc(29),
      O => \s_state1_carry__0_i_2_n_0\
    );
\s_state1_carry__0_i_3\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(26),
      I1 => hist_acc(27),
      O => \s_state1_carry__0_i_3_n_0\
    );
\s_state1_carry__0_i_4\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(24),
      I1 => hist_acc(25),
      O => \s_state1_carry__0_i_4_n_0\
    );
\s_state1_carry__0_i_5\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(22),
      I1 => hist_acc(23),
      O => \s_state1_carry__0_i_5_n_0\
    );
\s_state1_carry__0_i_6\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(20),
      I1 => hist_acc(21),
      O => \s_state1_carry__0_i_6_n_0\
    );
\s_state1_carry__0_i_7\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(18),
      I1 => hist_acc(19),
      O => \s_state1_carry__0_i_7_n_0\
    );
\s_state1_carry__0_i_8\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(16),
      I1 => hist_acc(17),
      O => \s_state1_carry__0_i_8_n_0\
    );
\s_state1_carry__0_i_9\: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(30),
      I1 => hist_acc(31),
      O => \s_state1_carry__0_i_9_n_0\
    );
s_state1_carry_i_1: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(14),
      I1 => hist_acc(15),
      O => s_state1_carry_i_1_n_0
    );
s_state1_carry_i_10: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(12),
      I1 => hist_acc(13),
      O => s_state1_carry_i_10_n_0
    );
s_state1_carry_i_11: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(10),
      I1 => hist_acc(11),
      O => s_state1_carry_i_11_n_0
    );
s_state1_carry_i_12: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(8),
      I1 => hist_acc(9),
      O => s_state1_carry_i_12_n_0
    );
s_state1_carry_i_13: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(6),
      I1 => hist_acc(7),
      O => s_state1_carry_i_13_n_0
    );
s_state1_carry_i_14: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(4),
      I1 => hist_acc(5),
      O => s_state1_carry_i_14_n_0
    );
s_state1_carry_i_15: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(2),
      I1 => hist_acc(3),
      O => s_state1_carry_i_15_n_0
    );
s_state1_carry_i_16: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(0),
      I1 => hist_acc(1),
      O => s_state1_carry_i_16_n_0
    );
s_state1_carry_i_2: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(12),
      I1 => hist_acc(13),
      O => s_state1_carry_i_2_n_0
    );
s_state1_carry_i_3: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(10),
      I1 => hist_acc(11),
      O => s_state1_carry_i_3_n_0
    );
s_state1_carry_i_4: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(8),
      I1 => hist_acc(9),
      O => s_state1_carry_i_4_n_0
    );
s_state1_carry_i_5: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(6),
      I1 => hist_acc(7),
      O => s_state1_carry_i_5_n_0
    );
s_state1_carry_i_6: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(4),
      I1 => hist_acc(5),
      O => s_state1_carry_i_6_n_0
    );
s_state1_carry_i_7: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(2),
      I1 => hist_acc(3),
      O => s_state1_carry_i_7_n_0
    );
s_state1_carry_i_8: unisim.vcomponents.LUT2
    generic map(
      INIT => X"E"
    )
        port map (
      I0 => hist_acc(0),
      I1 => hist_acc(1),
      O => s_state1_carry_i_8_n_0
    );
s_state1_carry_i_9: unisim.vcomponents.LUT2
    generic map(
      INIT => X"1"
    )
        port map (
      I0 => hist_acc(14),
      I1 => hist_acc(15),
      O => s_state1_carry_i_9_n_0
    );
start_read_i_1: unisim.vcomponents.LUT4
    generic map(
      INIT => X"F2AA"
    )
        port map (
      I0 => start_read,
      I1 => start_write_reg_n_0,
      I2 => m_state_reg_n_0,
      I3 => m_axis_tready,
      O => start_read_i_1_n_0
    );
start_read_reg: unisim.vcomponents.FDRE
    generic map(
      INIT => '1'
    )
        port map (
      C => m_axis_clk,
      CE => '1',
      D => start_read_i_1_n_0,
      Q => start_read,
      R => '0'
    );
start_write_i_1: unisim.vcomponents.LUT5
    generic map(
      INIT => X"BFFFAAAA"
    )
        port map (
      I0 => \FSM_onehot_s_state_reg_n_0_[2]\,
      I1 => s_axis_tvalid,
      I2 => start_read,
      I3 => \FSM_onehot_s_state_reg_n_0_[0]\,
      I4 => start_write_reg_n_0,
      O => start_write_i_1_n_0
    );
start_write_reg: unisim.vcomponents.FDRE
    generic map(
      INIT => '0'
    )
        port map (
      C => s_axis_clk,
      CE => '1',
      D => start_write_i_1_n_0,
      Q => start_write_reg_n_0,
      R => '0'
    );
end STRUCTURE;
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;
library UNISIM;
use UNISIM.VCOMPONENTS.ALL;
entity design_1_fpga_median_top_0_0 is
  port (
    s_axis_tready : out STD_LOGIC;
    s_axis_clk : in STD_LOGIC;
    s_axis_tvalid : in STD_LOGIC;
    s_axis_tlast : in STD_LOGIC;
    s_axis_tdata : in STD_LOGIC_VECTOR ( 31 downto 0 );
    m_axis_clk : in STD_LOGIC;
    m_axis_tready : in STD_LOGIC;
    m_axis_tvalid : out STD_LOGIC;
    m_axis_tlast : out STD_LOGIC;
    m_axis_tstrb : out STD_LOGIC_VECTOR ( 3 downto 0 );
    m_axis_tdata : out STD_LOGIC_VECTOR ( 7 downto 0 )
  );
  attribute NotValidForBitStream : boolean;
  attribute NotValidForBitStream of design_1_fpga_median_top_0_0 : entity is true;
  attribute CHECK_LICENSE_TYPE : string;
  attribute CHECK_LICENSE_TYPE of design_1_fpga_median_top_0_0 : entity is "design_1_fpga_median_top_0_0,fpga_median_top,{}";
  attribute DowngradeIPIdentifiedWarnings : string;
  attribute DowngradeIPIdentifiedWarnings of design_1_fpga_median_top_0_0 : entity is "yes";
  attribute IP_DEFINITION_SOURCE : string;
  attribute IP_DEFINITION_SOURCE of design_1_fpga_median_top_0_0 : entity is "module_ref";
  attribute X_CORE_INFO : string;
  attribute X_CORE_INFO of design_1_fpga_median_top_0_0 : entity is "fpga_median_top,Vivado 2020.1";
end design_1_fpga_median_top_0_0;

architecture STRUCTURE of design_1_fpga_median_top_0_0 is
  signal \<const1>\ : STD_LOGIC;
  signal \^m_axis_tlast\ : STD_LOGIC;
  attribute X_INTERFACE_INFO : string;
  attribute X_INTERFACE_INFO of m_axis_clk : signal is "xilinx.com:signal:clock:1.0 m_axis_clk CLK";
  attribute X_INTERFACE_PARAMETER : string;
  attribute X_INTERFACE_PARAMETER of m_axis_clk : signal is "XIL_INTERFACENAME m_axis_clk, ASSOCIATED_BUSIF m_axis, FREQ_HZ 150000000, FREQ_TOLERANCE_HZ 0, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, INSERT_VIP 0";
  attribute X_INTERFACE_INFO of m_axis_tlast : signal is "xilinx.com:interface:axis:1.0 m_axis TLAST";
  attribute X_INTERFACE_INFO of m_axis_tready : signal is "xilinx.com:interface:axis:1.0 m_axis TREADY";
  attribute X_INTERFACE_INFO of m_axis_tvalid : signal is "xilinx.com:interface:axis:1.0 m_axis TVALID";
  attribute X_INTERFACE_INFO of s_axis_clk : signal is "xilinx.com:signal:clock:1.0 s_axis_clk CLK";
  attribute X_INTERFACE_PARAMETER of s_axis_clk : signal is "XIL_INTERFACENAME s_axis_clk, ASSOCIATED_BUSIF s_axis, FREQ_HZ 150000000, FREQ_TOLERANCE_HZ 0, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, INSERT_VIP 0";
  attribute X_INTERFACE_INFO of s_axis_tlast : signal is "xilinx.com:interface:axis:1.0 s_axis TLAST";
  attribute X_INTERFACE_INFO of s_axis_tready : signal is "xilinx.com:interface:axis:1.0 s_axis TREADY";
  attribute X_INTERFACE_INFO of s_axis_tvalid : signal is "xilinx.com:interface:axis:1.0 s_axis TVALID";
  attribute X_INTERFACE_INFO of m_axis_tdata : signal is "xilinx.com:interface:axis:1.0 m_axis TDATA";
  attribute X_INTERFACE_PARAMETER of m_axis_tdata : signal is "XIL_INTERFACENAME m_axis, TDATA_NUM_BYTES 1, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 1, HAS_TKEEP 0, HAS_TLAST 1, FREQ_HZ 150000000, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, LAYERED_METADATA undef, INSERT_VIP 0";
  attribute X_INTERFACE_INFO of m_axis_tstrb : signal is "xilinx.com:interface:axis:1.0 m_axis TSTRB";
  attribute X_INTERFACE_INFO of s_axis_tdata : signal is "xilinx.com:interface:axis:1.0 s_axis TDATA";
  attribute X_INTERFACE_PARAMETER of s_axis_tdata : signal is "XIL_INTERFACENAME s_axis, TDATA_NUM_BYTES 4, TDEST_WIDTH 0, TID_WIDTH 0, TUSER_WIDTH 0, HAS_TREADY 1, HAS_TSTRB 0, HAS_TKEEP 0, HAS_TLAST 1, FREQ_HZ 150000000, PHASE 0.000, CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0, LAYERED_METADATA undef, INSERT_VIP 0";
begin
  m_axis_tlast <= \^m_axis_tlast\;
  m_axis_tstrb(3) <= \<const1>\;
  m_axis_tstrb(2) <= \<const1>\;
  m_axis_tstrb(1) <= \<const1>\;
  m_axis_tstrb(0) <= \<const1>\;
  m_axis_tvalid <= \^m_axis_tlast\;
VCC: unisim.vcomponents.VCC
     port map (
      P => \<const1>\
    );
inst: entity work.design_1_fpga_median_top_0_0_fpga_median_top
     port map (
      m_axis_clk => m_axis_clk,
      m_axis_tdata(7 downto 0) => m_axis_tdata(7 downto 0),
      m_axis_tlast => \^m_axis_tlast\,
      m_axis_tready => m_axis_tready,
      s_axis_clk => s_axis_clk,
      s_axis_tdata(31 downto 0) => s_axis_tdata(31 downto 0),
      s_axis_tlast => s_axis_tlast,
      s_axis_tready => s_axis_tready,
      s_axis_tvalid => s_axis_tvalid
    );
end STRUCTURE;
