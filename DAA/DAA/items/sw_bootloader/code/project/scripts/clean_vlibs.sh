#!/bin/bash

set -e

export workspaceFolder=../../../
VLIBS_DIR=$(pwd)/../../../../Vlibs

# Colores ANSI
GREEN="\033[0;32m"
RED="\033[0;31m"
RESET="\033[0m"

clean_module() {
    local MODULE_NAME=$1
    local MODULE_PATH="${VLIBS_DIR}/${MODULE_NAME}/code/project/cmake"

    echo "Cleaning ${MODULE_NAME} ..."

    mkdir -p "${MODULE_PATH}/build"
    rm -r "${MODULE_PATH}/build"
    # rm -rf *
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
    clean_module "$MODULE"
done

echo -e "\n${GREEN}Todos los módulos han sido limpiados correctamente.${RESET}\n"
