#!/bin/bash

if [ ! -x "$(which petalinux-create)" ]; then
    echo "Petalinux tools not found"
    exit 1
fi

if [ $# -lt 2 ]; then
    echo "USAGE: $0 [PROJECT NAME] [BSP]"
    exit 1
fi


cd $1
petalinux-package --force --bsp -o $2 -p .

exit 0
