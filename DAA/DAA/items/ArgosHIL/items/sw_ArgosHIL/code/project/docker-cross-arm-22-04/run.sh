#!/bin/bash
set -e

# Auto-detecta la raiz del repo desde la ubicacion de este script
# .../items/ArgosHIL/items/sw_ArgosHIL/code/project/docker-cross-arm-22-04/run.sh
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../../../../../.." && pwd)"
REPO_NAME="$(basename "$REPO_ROOT")"

DOCKER_DIR="$SCRIPT_DIR"

# Nombre de producto: $1 o nombre del repo (en minusculas)
PRODUCT="$(echo "${1:-$REPO_NAME}" | tr '[:upper:]' '[:lower:]')"

VSCODE_HOST_DIR="$DOCKER_DIR/vscode/$USER"
mkdir -p "$VSCODE_HOST_DIR"

docker run -it \
     -v "$REPO_ROOT":/workspace/:rw \
     -v "$HOME":/home_host:rw \
     -v "$VSCODE_HOST_DIR":/workspace/.vscode:rw \
     --workdir /workspace \
     -e CROSS_ENVIROMENT=/usr/aarch64-xilinx-linux \
     -e CROSS_ENV_PATH=/usr/aarch64-xilinx-linux \
     -e COMPILER_PREFIX=aarch64-linux-gnu- \
     --name "${PRODUCT}_cross_build_aarch64_arm-2204" \
     --rm aarch64-linux-cross-arm-2204
