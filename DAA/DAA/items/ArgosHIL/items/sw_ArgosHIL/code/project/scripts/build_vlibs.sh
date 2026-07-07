#!/bin/bash
# Cross-compila las Vlibs necesarias para wvlibs (estaticas .a)
set -e

COMPILER_PREFIX=${COMPILER_PREFIX:-aarch64-linux-gnu-}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../../../../.." && pwd)"
VLIBS_DIR="${REPO_ROOT}/items/sw/sw_daa/items/_sw_perception/items/Vlibs"

VLIBS_LIBS="geomodel maverick pring first base bsp media devices DFS2 stanag"

echo "==> VLIBS_DIR = ${VLIBS_DIR}"

for lib in ${VLIBS_LIBS}; do
    LIB_CMAKE="${VLIBS_DIR}/${lib}/code/project/cmake"
    if [ ! -d "${LIB_CMAKE}" ]; then
        echo "ERROR: no existe ${LIB_CMAKE}"
        exit 1
    fi
    echo "==> Compilando vlib: ${lib}"
    mkdir -p "${LIB_CMAKE}/build"
    cd "${LIB_CMAKE}/build"
    cmake -D CMAKE_BUILD_TYPE=Release \
          -D CMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
          -D CMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
          ..
    make -j"$(nproc)"
done

echo "==> Vlibs compiladas OK"
