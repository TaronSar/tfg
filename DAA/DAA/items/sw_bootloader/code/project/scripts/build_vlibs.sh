#!/bin/bash

set -e

VLIBS_DIR=$(pwd)/../../../../Vlibs  # Path to Vlibs
COMPILER_PREFIX=aarch64-none-elf-   # For baremetal compilation

mkdir -p "${VLIBS_DIR}/lib"

# ANSI Colors
GREEN="\033[0;32m"
RESET="\033[0m"

build_module() {
    local MODULE_NAME=$1
    local MODULE_PATH="${VLIBS_DIR}/${MODULE_NAME}/code/project/cmake"

    echo -e "\n===================================="
    echo " Configuring and building ${MODULE_NAME} ..."
    echo "===================================="

    mkdir -p "${MODULE_PATH}/build"
    cd "${MODULE_PATH}/build"

    cmake .. \
        -D CMAKE_BUILD_TYPE=Release \
        -D CMAKE_C_COMPILER_WORKS=1 \
        -D CMAKE_CXX_COMPILER_WORKS=1 \
        -D CMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
        -D CMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++

    make -j$(nproc)

    cp *.a "${VLIBS_DIR}/lib/"
}

MODULES=(
    bsp
    base
    first
    geomodel
    maverick
    devices
    media
    DFS2
    stanag
)

for MODULE in "${MODULES[@]}"; do
    build_module "$MODULE"
done

echo -e "\n${GREEN}Todos los módulos se han compilado y copiado a lib${RESET}\n"
