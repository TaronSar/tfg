#!/bin/bash

xsa=$1

current_path=$(pwd)

base_path=$(pwd)/../../../../../..
cd $base_path
base_path=$(pwd)
xsa_path="$base_path/fpga_altimeter/items/fpga_spi_PLL_BGT_PGA/code/project/VITIS/SPI_PLL_BGT_PGA.xsa"

cd $current_path

echo $xsa_path
xsa=${1:-$xsa_path}

if [ -z "$xsa" ]; then
    echo "USAGE: $0 [XSA FILE]"
else
    echo "Creating platform from: $1"
    xsct -eval "source platform.tcl; create_platform $xsa"
fi
