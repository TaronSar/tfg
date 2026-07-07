set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]
set_property CONFIG_VOLTAGE 3.3 [current_design]
set_property CFGBVS VCCO [current_design]


## ChipKit SPI
#CLK
set_property -dict {PACKAGE_PIN AC14 IOSTANDARD LVCMOS33} [get_ports SPI_0_sck_io]
#CS0
set_property -dict {PACKAGE_PIN AB12 IOSTANDARD LVCMOS33} [get_ports SPI_0_ss_io]
#CS1
set_property -dict {PACKAGE_PIN AC12 IOSTANDARD LVCMOS33} [get_ports SPI_0_ss1_o]
#CS2
set_property -dict {PACKAGE_PIN AE12 IOSTANDARD LVCMOS33} [get_ports SPI_0_ss2_o]
#MOSI
set_property -dict {PACKAGE_PIN AF12 IOSTANDARD LVCMOS33} [get_ports SPI_0_io0_io]
#MISO
set_property -dict {PACKAGE_PIN AD13 IOSTANDARD LVCMOS33} [get_ports SPI_0_io1_io]

################################## DIGITAL PINS ##################################

#IO_PLL_CE 
set_property -dict {PACKAGE_PIN AD14 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[0]} ]
#IO_PLL_TRIG2
set_property -dict {PACKAGE_PIN AG12 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[1]} ]
#IO_PLL_MUX_IN
set_property -dict {PACKAGE_PIN AH12 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[2]} ]
#IO_PLL_MOD
set_property -dict {PACKAGE_PIN AE13 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[3]} ]
#IO_PLL_TRIG1
set_property -dict {PACKAGE_PIN AF13 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[4]} ]
#EMPTY
set_property -dict {PACKAGE_PIN AH13 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[5]} ]

set_property -dict {PACKAGE_PIN AH14 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[6]} ]

set_property -dict {PACKAGE_PIN AJ13 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[7]} ]

set_property -dict {PACKAGE_PIN AJ14 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[8]} ]

set_property -dict {PACKAGE_PIN AK12 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[9]} ]

set_property -dict {PACKAGE_PIN AK13 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[10]} ]

set_property -dict {PACKAGE_PIN AB14 IOSTANDARD LVCMOS33} [get_ports {GPIO_0_tri_io[11]} ]