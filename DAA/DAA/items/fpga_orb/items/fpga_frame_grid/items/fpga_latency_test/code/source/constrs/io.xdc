
set_property PACKAGE_PIN AK13 [get_ports {cam_gpio[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {cam_gpio[0]}]
set_property PULLUP true [get_ports {cam_gpio[0]}]

set_property PACKAGE_PIN G16 [get_ports uart_rx]
set_property PACKAGE_PIN J15 [get_ports uart_tx]

set_property IOSTANDARD LVCMOS33 [get_ports uart_rx]
set_property IOSTANDARD LVCMOS33 [get_ports uart_tx]



set_property IOSTANDARD LVCMOS33 [get_ports {dbg0[0]}]
set_property PACKAGE_PIN AM13 [get_ports {dbg0[0]}]
set_property IOSTANDARD LVCMOS33 [get_ports {dbg1[0]}]
set_property PACKAGE_PIN AP12 [get_ports {dbg1[0]}]

set_property IOSTANDARD LVCMOS33 [get_ports {xtrig[0]}]
set_property PACKAGE_PIN G19 [get_ports {xtrig[0]}]



set_property PACKAGE_PIN AN13 [get_ports cam_i2c_scl_io]
set_property PACKAGE_PIN AM14 [get_ports cam_i2c_sda_io]

set_property IOSTANDARD LVCMOS33 [get_ports cam_i2c_scl_io]
set_property IOSTANDARD LVCMOS33 [get_ports cam_i2c_sda_io]

set_property PULLUP true [get_ports cam_i2c_scl_io]
set_property PULLUP true [get_ports cam_i2c_sda_io]



set_operating_conditions -process maximum

set_property SLEW SLOW [get_ports uart_tx]
set_property PULLUP true [get_ports uart_rx]
