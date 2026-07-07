#!/bin/bash
CROSS_ENV_PATH_SCRIPT=${CROSS_ENVIROMENT}

if [[ -v NOT_CROSS_ENV ]]; then
    CROSS_ENV_PATH_SCRIPT=0
else
echo "CROSS_ENV_PATH ${CROSS_ENV_PATH_SCRIPT}"
fi

if [ "$#" -lt 1 ]; then
    echo "Error: test name as argument is required."
    exit 1
fi

cd ../cmake/

echo "Configuring and building DAA ..."
#cd /workspace/code/ORB_SLAM3/
if [ ! -d "build" ]
then
    mkdir build
fi

if [ "${DAA_TEXAS}" = "1" ]; then
    echo "Compiling for Texas Instruments..."
    export COMPILER_PREFIX="/ti_toolchain/arm-gnu-toolchain-13.2.Rel1-x86_64-aarch64-none-linux-gnu/bin/aarch64-none-linux-gnu-"
else
    echo "Compiling SW version ..."
fi

CMAKE_FLAGS="-D CMAKE_BUILD_TYPE=${BUILD_TYPE} \
                -D CMAKE_DAA_TEXAS=${DAA_TEXAS} \
                -D SRC_MAIN=$1/source/main.cpp \
                -D CROSS_ENV_PATH=${CROSS_ENV_PATH_SCRIPT} \
                -D CMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
                -D CMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
                -D CMAKE_CUDA_12=${CUDA_12}
"

if [ "${DAA_TEXAS}" = "1" ]; then
    CMAKE_FLAGS+="\
    "
fi

cd build/ && cmake $CMAKE_FLAGS .. && make -j12
