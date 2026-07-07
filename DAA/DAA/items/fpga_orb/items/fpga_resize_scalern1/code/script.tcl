############################################################
## This file is generated automatically by Vivado HLS.
## Please DO NOT edit it.
## Copyright (C) 1986-2020 Xilinx, Inc. All Rights Reserved.
############################################################
open_project resize_scalern1
set_top resize_scalern1
add_files ./resize_scalern1.cpp
add_files ./resize_scalern1.h
add_files -tb ./resize_scalern1_tb.cpp -cflags "-Wno-unknown-pragmas" -csimflags "-Wno-unknown-pragmas"
open_solution "solution1"
#set_part {xczu7ev-ffvc1156-2-e}
#set_part {xczu5ev-sfvc784-1-e}
set_part {xczu15eg-ffvb1156-2-i}
create_clock -period 8 -name default
config_sdx -optimization_level none -target none
config_export -format ip_catalog -rtl verilog -vivado_optimization_level 2 -vivado_phys_opt place -vivado_report_level 0
#source "./resize_scalern1/solution1/directives.tcl"
#csim_design -O
csynth_design
#cosim_design -O
export_design -rtl verilog -format ip_catalog
