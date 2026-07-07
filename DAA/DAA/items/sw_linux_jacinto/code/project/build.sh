#!/bin/bash

# This script builds the Linux Device Tree for Jacinto platforms.
# It assumes that the necessary environment, SDKs, and toolchains are already set up.
#
# Usage: ./build.sh [SDK_PATH]
# Example: ./build.sh /opt/ti/sdk-linux-j784s4-evm-11-01-00-03

set -e

# Check if SDK path is provided as argument, otherwise use default
if [ $# -eq 1 ]; then
    SDK_PATH="$1"
elif [ $# -eq 0 ]; then
    SDK_PATH="/opt/ti/sdk-linux-j784s4-evm-11-01-00-03"
    echo "Using default SDK path: $SDK_PATH"
else
    echo "Usage: $0 [SDK_PATH]"
    echo "Example: $0 /opt/ti/sdk-linux-j784s4-evm-11-01-00-03"
    exit 1
fi

# Validate SDK path exists
if [ ! -d "$SDK_PATH" ]; then
    echo "Error: SDK path does not exist: $SDK_PATH"
    exit 1
fi

echo "Using SDK path: $SDK_PATH"

# Define path to dts to add
DTS_PATH="../dts"

# Define output directory for the built device tree blobs
# Find the kernel directory dynamically
KERNEL_DIR=$(find "$SDK_PATH/board-support" -name "ti-linux-kernel-*" -type d | head -n 1)
if [ -z "$KERNEL_DIR" ]; then
    echo "Error: Could not find kernel directory in $SDK_PATH/board-support"
    exit 1
fi

OUTPUT_PATH="$KERNEL_DIR/arch/arm64/boot/dts/ti"

# Define Rules.make path
RULES_MAKE_PATH="$SDK_PATH/Rules.make"

# Copy the DTS files to the kernel's dts directory
cp ${DTS_PATH}/*.dts ${OUTPUT_PATH}/

# Update KERNEL_DEVICETREE_PREFIX in Rules.make to include new DTS files
echo "Updating KERNEL_DEVICETREE_PREFIX in Rules.make..."

# Backup the original Rules.make
cp ${RULES_MAKE_PATH} ${RULES_MAKE_PATH}.backup

# Update the KERNEL_DEVICETREE_PREFIX line
sed -i 's|^KERNEL_DEVICETREE_PREFIX=.*|KERNEL_DEVICETREE_PREFIX=ti/k3-j784s4\|ti/k3-j7200-evm-mcspi-loopback\|ti/k3-fpdlink\|ti/k3-v3link\|ti/k3-am69-sk\|ti/k3-j721s2-evm-csi2-ov5640\|ti/k3-j721s2-evm-fusion\|ti/k3-j721s2-evm-ub954\|ti/k3-j784s4-evm-tda4ap-profile\|ti/k3-j784s4-evm-tda4ah-profile\|ti/k3-j784s4-evm-tda4vh-profile\|ti/k3-j784s4-evm-tda4vp-profile|' ${RULES_MAKE_PATH}

echo "KERNEL_DEVICETREE_PREFIX updated successfully."

# Validate that all required paths exist
if [ ! -d "$OUTPUT_PATH" ]; then
    echo "Error: Kernel DTS directory does not exist: $OUTPUT_PATH"
    exit 1
fi

if [ ! -f "$RULES_MAKE_PATH" ]; then
    echo "Error: Rules.make file does not exist: $RULES_MAKE_PATH"
    exit 1
fi

# Navigate to the kernel source directory
cd "$SDK_PATH"

make linux-dtbs

echo "Device Tree build completed successfully."
