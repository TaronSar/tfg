#!/bin/bash

cd ../cmake/

echo "Configuring and building hello world ..."

if [ ! -d "build" ]
then
    mkdir build
fi
cd build/ && \
    cmake -D CMAKE_BUILD_TYPE=Release \
    -D CCPREFIX=aarch64-none-elf- \
    -D LDSCRIPT=../../../source/lscript.ld \
    .. && \
    make
