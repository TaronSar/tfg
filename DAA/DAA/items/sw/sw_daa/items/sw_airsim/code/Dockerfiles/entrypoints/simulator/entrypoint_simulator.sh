#!/bin/bash
set -e

# Create records directory if it doesn't exist
mkdir -p /home/catec/records

WORLD_ROOT="/home/catec/simulator/${SIMULATOR_WORLD_NAME}/LinuxNoEditor"
FILE="${WORLD_ROOT}/${SIMULATOR_WORLD_NAME}.sh"
LOG_DIR="/home/catec/records/unreal_logs"
LOG_FILE="${LOG_DIR}/${SIMULATOR_WORLD_NAME}.log"

mkdir -p "${LOG_DIR}"

if test -f "$FILE"; then
    "${FILE}" -windowed -log -abslog="${LOG_FILE}"
else
    echo "$FILE does not exist."
    exit 1
fi