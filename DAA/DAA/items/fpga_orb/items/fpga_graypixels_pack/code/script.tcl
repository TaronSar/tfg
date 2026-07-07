# Copyright (C) 2021 Xilinx, Inc
#
# SPDX-License-Identifier: BSD-3-Clause

open_project -upgrade graypixels_pack
set_top graypixels_pack
add_files graypixels_pack.cpp
add_files -tb graypixels_pack_tb.cpp
open_solution "solution1"
#set_part {xczu7ev-ffvc1156-2-i}
#set_part {xczu5ev-sfvc784-1-e}
set_part {xczu15eg-ffvb1156-2-i}
create_clock -period 3.3
csynth_design
export_design -format ip_catalog -description "Graypixels packer" -display_name "Graypixels pack"
exit
