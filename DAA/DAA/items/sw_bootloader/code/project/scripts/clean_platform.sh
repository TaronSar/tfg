#!/bin/bash

ZUSP_DIR=$(realpath "../../../../sw_zusp")
FILES_AND_DIRS=(
    "$ZUSP_DIR/code/.metadata"
    "$ZUSP_DIR/code/lib"
    "$ZUSP_DIR/code/patform"
    "$ZUSP_DIR/code/.analytics"
    "$ZUSP_DIR/code/IDE.log"
    "$ZUSP_DIR/code/project/scripts/.Xil"
)

for path in "${FILES_AND_DIRS[@]}"; do
    if [ -e "$path" ]; then
        echo "Borrando: $path"
        rm -rf "$path"
    else
        echo "No existe: $path"
    fi
done
