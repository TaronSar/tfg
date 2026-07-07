proc flash {  }  { 

connect -url tcp:127.0.0.1:3121
targets -set -nocase -filter {name =~"APU*"}
rst -system

after 3000

targets -set -filter {jtag_cable_name =~ "Digilent JTAG-HS1 210512180081" && level==0 && jtag_device_ctx=="jsn-JTAG-HS1-210512180081-03736093-0"}

fpga -file "../../platform/hw/SPI_BGTPGA.bit"

targets -set -nocase -filter {name =~"APU*"}
loadhw -hw "../../platform/hw/SPI_BGTPGA.xsa" -mem-ranges [list {0x40000000 0xbfffffff}] -regs
configparams force-mem-access 1

targets -set -nocase -filter {name =~"APU*"}
source "../../platform/hw/ps7_init.tcl"
ps7_init
ps7_post_config

targets -set -nocase -filter {name =~ "*A9*#0"}
dow "../cmake/build/SPI_BGTPGA.elf"
configparams force-mem-access 0
after 500

targets -set -nocase -filter {name =~"APU*"}

} 
