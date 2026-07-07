##!/bin/bash

VLIBS_DIR=$(pwd)/../../../../Vlibs
##COMPILER_PREFIX=/opt/gcc-arm-9.2-2019.12-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-
COMPILER_PREFIX=aarch64-none-elf-

cd ${VLIBS_DIR}

if [ ! -d "lib" ]
then
    mkdir lib
fi

cd ${VLIBS_DIR}/bsp/code/project/cmake

echo "Configuring and building Vlibs bsp ..."
#cd /workspace/code/ORB_SLAM3/
if [ ! -d "build" ]
then
    mkdir build
fi
cd build/ && \
    cmake -D CMAKE_BUILD_TYPE=Release \
    -D CCPREFIX=${COMPILER_PREFIX} \
    .. && \
    make
cp *.a ${VLIBS_DIR}/lib/.