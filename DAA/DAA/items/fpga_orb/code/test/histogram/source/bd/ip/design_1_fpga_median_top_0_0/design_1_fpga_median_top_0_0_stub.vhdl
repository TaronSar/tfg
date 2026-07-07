-- Copyright 1986-2020 Xilinx, Inc. All Rights Reserved.
-- --------------------------------------------------------------------------------
-- Tool Version: Vivado v.2020.1 (lin64) Build 2902540 Wed May 27 19:54:35 MDT 2020
-- Date        : Thu Jun 20 09:13:26 2024
-- Host        : user-VirtualBox running 64-bit Ubuntu 18.04.6 LTS
-- Command     : write_vhdl -force -mode synth_stub
--               /home/vmm6/projects_shared/Vision/repo/DAA/items/fpga_orb/code/test/histogram/source/bd/ip/design_1_fpga_median_top_0_0/design_1_fpga_median_top_0_0_stub.vhdl
-- Design      : design_1_fpga_median_top_0_0
-- Purpose     : Stub declaration of top-level module interface
-- Device      : xczu15eg-ffvb1156-2-i
-- --------------------------------------------------------------------------------
library IEEE;
use IEEE.STD_LOGIC_1164.ALL;

entity design_1_fpga_median_top_0_0 is
  Port ( 
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

end design_1_fpga_median_top_0_0;

architecture stub of design_1_fpga_median_top_0_0 is
attribute syn_black_box : boolean;
attribute black_box_pad_pin : string;
attribute syn_black_box of stub : architecture is true;
attribute black_box_pad_pin of stub : architecture is "s_axis_tready,s_axis_clk,s_axis_tvalid,s_axis_tlast,s_axis_tdata[31:0],m_axis_clk,m_axis_tready,m_axis_tvalid,m_axis_tlast,m_axis_tstrb[3:0],m_axis_tdata[7:0]";
attribute X_CORE_INFO : string;
attribute X_CORE_INFO of stub : architecture is "fpga_median_top,Vivado 2020.1";
begin
end;
