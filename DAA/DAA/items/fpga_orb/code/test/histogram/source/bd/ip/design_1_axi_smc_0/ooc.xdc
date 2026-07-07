# aclk {FREQ_HZ 150000000 CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk0 PHASE 0.000} aclk1 {FREQ_HZ 100000000 CLK_DOMAIN design_1_zynq_ultra_ps_e_0_0_pl_clk2 PHASE 0.000}
# Clock Domain: design_1_zynq_ultra_ps_e_0_0_pl_clk0
create_clock -name aclk -period 6.667 [get_ports aclk]
# Clock Domain: design_1_zynq_ultra_ps_e_0_0_pl_clk2
create_clock -name aclk1 -period 10.000 [get_ports aclk1]
# Generated clocks
