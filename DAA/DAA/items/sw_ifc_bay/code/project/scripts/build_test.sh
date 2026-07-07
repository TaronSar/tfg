#!/bin/bash

#COMPILER_PREFIX=/opt/gcc-arm-9.2-2019.12-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-
COMPILER_PREFIX=aarch64-linux-gnu-

cd ../cmake/

echo "Configuring and building HIL software ..."

if [ ! -d "build" ]
then
    mkdir build
fi
cd build/ && \
    cmake -D CMAKE_BUILD_TYPE=Release \
    -D CMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
    -D CMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
    -D CROSS_ENV_PATH=/usr/aarch64-xilinx-linux \
    -D MAIN_FILE=$1 \
    .. && \
    make