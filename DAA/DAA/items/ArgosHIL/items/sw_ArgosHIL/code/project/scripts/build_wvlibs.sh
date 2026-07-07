#!/bin/bash
# Cross-compila wvlibs y genera libwvlibs.a (mergea wvlibs + vlibs)
set -e

COMPILER_PREFIX=${COMPILER_PREFIX:-aarch64-linux-gnu-}
export COMPILER_PREFIX

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../../../../.." && pwd)"
WVLIBS_DIR="${REPO_ROOT}/items/sw/sw_daa/items/_sw_perception/items/sw_gnssdenied/items/sw_wvlibs"

echo "==> WVLIBS_DIR = ${WVLIBS_DIR}"

# 1) Build CMake de wvlibs
mkdir -p "${WVLIBS_DIR}/code/project/cmake/build"
cd "${WVLIBS_DIR}/code/project/cmake/build"
cmake -D CMAKE_BUILD_TYPE=Release \
      -D CMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
      -D CMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
      ..
make -j"$(nproc)"

# 2) Mergear con las Vlibs en libwvlibs.a
cd "${WVLIBS_DIR}/code/project/scripts"
bash generate_item_lib.sh

echo "==> libwvlibs.a generada en ${WVLIBS_DIR}/code/project/cmake/build/"
ls -la "${WVLIBS_DIR}/code/project/cmake/build/libwvlibs.a"
