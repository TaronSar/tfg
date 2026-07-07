


set_operating_conditions -process maximum



set_property IOSTANDARD LVCMOS18 [get_ports IIC_0_0_scl_io]
set_property IOSTANDARD LVCMOS18 [get_ports IIC_0_0_sda_io]
set_property DRIVE 12 [get_ports IIC_0_0_scl_io]
set_property DRIVE 12 [get_ports IIC_0_0_sda_io]




set_property IOSTANDARD LVCMOS18 [get_ports UART_0_0_rxd]
set_property IOSTANDARD LVCMOS18 [get_ports UART_0_0_txd]

set_property PACKAGE_PIN V11 [get_ports UART_0_0_rxd]
set_property PACKAGE_PIN V12 [get_ports UART_0_0_txd]

set_property DIFF_TERM_ADV TERM_100 [get_ports {mipi_phy_if_0_data_n[0]}]
set_property DIFF_TERM_ADV TERM_100 [get_ports {mipi_phy_if_0_data_p[0]}]

# XCLR
set_property PACKAGE_PIN AB8 [get_ports {GPIO_0_0_tri_io[0]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[1]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[0]}]
set_property DRIVE 12 [get_ports {GPIO_0_0_tri_io[1]}]
set_property DRIVE 12 [get_ports {GPIO_0_0_tri_io[0]}]

set_property IOSTANDARD MIPI_DPHY_DCI [get_ports {mipi_phy_if_0_data_p[0]}]
set_property IOSTANDARD MIPI_DPHY_DCI [get_ports {mipi_phy_if_0_data_n[0]}]
set_property IOSTANDARD MIPI_DPHY_DCI [get_ports mipi_phy_if_0_clk_p]
set_property IOSTANDARD MIPI_DPHY_DCI [get_ports mipi_phy_if_0_clk_n]

# POC EN
set_property PACKAGE_PIN W7 [get_ports {GPIO_0_0_tri_io[1]}]
# XTRIG
set_property PACKAGE_PIN AC8 [get_ports {GPIO_0_0_tri_io[2]}]
# XHS
set_property PACKAGE_PIN AC6 [get_ports {GPIO_0_0_tri_io[3]}]
# XVS
set_property PACKAGE_PIN AB6 [get_ports {GPIO_0_0_tri_io[4]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[4]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[3]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[2]}]

# CAN 0 STB
set_property PACKAGE_PIN W12 [get_ports {GPIO_0_0_tri_io[5]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[5]}]

# CAN 0 RES
set_property PACKAGE_PIN W11 [get_ports {GPIO_0_0_tri_io[6]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[6]}]

# CAN 1 STB
set_property PACKAGE_PIN T12 [get_ports {GPIO_0_0_tri_io[7]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[7]}]

# CAN 1 RES
set_property PACKAGE_PIN R12 [get_ports {GPIO_0_0_tri_io[8]}]
set_property IOSTANDARD LVCMOS18 [get_ports {GPIO_0_0_tri_io[8]}]

set_property IOSTANDARD LVCMOS18 [get_ports CAN_0_0_rx]
set_property IOSTANDARD LVCMOS18 [get_ports CAN_0_0_tx]
set_property IOSTANDARD LVCMOS18 [get_ports CAN_1_0_rx]
set_property IOSTANDARD LVCMOS18 [get_ports CAN_1_0_tx]
set_property PACKAGE_PIN T13 [get_ports CAN_0_0_rx]
set_property PACKAGE_PIN R13 [get_ports CAN_0_0_tx]
set_property PACKAGE_PIN T10 [get_ports CAN_1_0_rx]
set_property PACKAGE_PIN U10 [get_ports CAN_1_0_tx]

set_property PACKAGE_PIN Y4 [get_ports IIC_2_scl_io]
set_property PACKAGE_PIN Y3 [get_ports IIC_2_sda_io]
set_property IOSTANDARD LVCMOS18 [get_ports IIC_2_sda_io]
set_property IOSTANDARD LVCMOS18 [get_ports IIC_2_scl_io]
set_property PULLUP true [get_ports IIC_2_scl_io]
set_property PULLUP true [get_ports IIC_2_sda_io]
set_property SLEW SLOW [get_ports IIC_2_sda_io]
set_property SLEW FAST [get_ports IIC_2_scl_io]
set_property DRIVE 12 [get_ports IIC_2_scl_io]
set_property DIFF_TERM_ADV TERM_NONE [get_ports mipi_phy_if_0_clk_n]
set_property DIFF_TERM_ADV TERM_NONE [get_ports mipi_phy_if_0_clk_p]




set_property OFFCHIP_TERM NONE [get_ports IIC_2_scl_io]
set_property OFFCHIP_TERM NONE [get_ports IIC_2_sda_io]
