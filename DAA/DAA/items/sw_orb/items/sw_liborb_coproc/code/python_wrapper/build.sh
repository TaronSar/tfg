#!/bin/bash

COMPILER_PREFIX=aarch64-linux-gnu-

mkdir -p ../build/python_wrapper
cd ../build/python_wrapper
cmake -D CMAKE_BUILD_TYPE=Release \
    -D PYTHON_EXECUTABLE=$(which python3.12) \
    -D CMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
    -D CMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
    -D CROSS_ENV_PATH=${CROSS_ENVIROMENT} \
    ../../python_wrapper && \
make -j12
