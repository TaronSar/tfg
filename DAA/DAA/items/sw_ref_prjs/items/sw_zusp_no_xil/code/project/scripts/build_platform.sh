#!/bin/bash

PRJ_DIR=$(pwd)/../..

echo "Building psu_cortexa53_0 ..."
cd $PRJ_DIR/platform/psu_cortexa53_0/domain_psu_cortexa53_0/bsp
make

echo "Building FSBL ..."
cd $PRJ_DIR/platform/zynqmp_fsbl
make

echo "Building PMUFW ..."
cd $PRJ_DIR/platform/zynqmp_pmufw
make