############################################################
## This file is generated automatically by Vitis HLS.
## Please DO NOT edit it.
## Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
## Copyright 2022-2023 Advanced Micro Devices, Inc. All Rights Reserved.
############################################################
open_project project_red
set_top imganalysis
add_files imganalysis_src/imganalysis.cpp
add_files imganalysis_src/imganalysis.hpp
add_files -tb imganalysis_src/img_gray.h -cflags "-Wno-unknown-pragmas"
add_files -tb imganalysis_src/imganalysis_tb.cpp -cflags "-Wno-unknown-pragmas"
open_solution "solution1" -flow_target vivado
set_part {xczu15eg-ffvb1156-2-i}
create_clock -period 3.33 -name default
config_export -description {Image statistics: histogram, max value, min value, mean, num pixels} -display_name imganalysis -format ip_catalog -rtl verilog
source "./project_red/solution1/directives.tcl"
csim_design
csynth_design
cosim_design
export_design -rtl verilog -format ip_catalog
