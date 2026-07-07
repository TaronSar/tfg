proc flash {  }  { 

connect -url tcp:127.0.0.1:3121
targets -set -nocase -filter {name =~"APU*"}
rst -system

after 3000

targets -set -filter {jtag_cable_name =~ "Digilent JTAG-HS1 210512180081" && level==0 && jtag_device_ctx=="jsn-JTAG-HS1-210512180081-03736093-0"}

fpga -file "../../platform/hw/dma_rd_TEST.bit"

targets -set -nocase -filter {name =~"APU*"}
loadhw -hw "../../platform/hw/dma_rd_TEST.xsa" -mem-ranges [list {0x40000000 0xbfffffff}] -regs
configparams force-mem-access 1

targets -set -nocase -filter {name =~"APU*"}
source "../../platform/hw/ps7_init.tcl"
ps7_init
ps7_post_config

targets -set -nocase -filter {name =~ "*A9*#0"}
dow "../cmake/build/dma_rd.elf"
configparams force-mem-access 0
after 500

targets -set -nocase -filter {name =~"APU*"}
con
} 
