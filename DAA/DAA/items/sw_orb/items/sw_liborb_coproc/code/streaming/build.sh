#!/bin/bash

COMPILER_PREFIX=aarch64-linux-gnu-

mkdir -p ../build/streaming
cd ../build/streaming
cmake -D CMAKE_BUILD_TYPE=Release \
    -D CMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
    -D CMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
    -D CROSS_ENV_PATH=${CROSS_ENVIROMENT} \
    ../../streaming
make
#    -D OpenCV_PATH=/usr/aarch64-xilinx-linux/lib64/cmake/opencv4 \
