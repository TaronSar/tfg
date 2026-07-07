#!/bin/bash

# Set vivado_hls route - 2019.1 version mandatory
VIVADO_HLS=/opt/Xilinx/old/2019.1/bin/vivado_hls

cd ../../code
$VIVADO_HLS script.tcl

