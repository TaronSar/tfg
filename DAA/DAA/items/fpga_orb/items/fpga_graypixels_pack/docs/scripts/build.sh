#!/bin/bash

# Set vitis_hls
VIVADO_HLS=/opt/Xilinx/Vitis/2020.1/bin/vitis_hls


cd ../../code
$VIVADO_HLS script.tcl

