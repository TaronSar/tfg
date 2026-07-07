#!/bin/bash

set -e

cd ../cmake/

if [ ! -d "build" ]
then
    mkdir build
fi
cd build/ && \
    cmake -D CMAKE_BUILD_TYPE=Debug \
    -D SRC_MAIN=../../../source/boot/main.cpp \
    -D CCPREFIX=aarch64-none-elf- \
    -D LDSCRIPT=../../../source/lscript.ld \
    -D APP_NAME=bootloader \
    .. && \
    make -j$(nproc)

cd ..
if [ ! -d "build0001" ]
then
    mkdir build0001
fi
cd build0001/ && \
    cmake -D CMAKE_BUILD_TYPE=Debug \
    -D SRC_MAIN=../../../source/0001/main.cpp \
    -D CCPREFIX=aarch64-none-elf- \
    -D LDSCRIPT=../../../source/lscript.ld \
    -D APP_NAME=0001 \
    .. && \
    make -j$(nproc)

cd ..
if [ ! -d "build0002" ]
then
    mkdir build0002
fi
cd build0002/ && \
    cmake -D CMAKE_BUILD_TYPE=Debug \
    -D SRC_MAIN=../../../source/0002/main.cpp \
    -D CCPREFIX=aarch64-none-elf- \
    -D LDSCRIPT=../../../source/lscript.ld \
    -D APP_NAME=0002 \
    .. && \
    make -j$(nproc)
