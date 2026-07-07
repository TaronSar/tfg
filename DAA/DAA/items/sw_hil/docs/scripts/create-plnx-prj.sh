#!/bin/bash

if [ ! -x "$(which petalinux-create)" ]; then
    echo "Petalinux tools not found"
    exit 1
fi

if [ $# -lt 2 ]; then
    echo "USAGE: $0 [PROJECT NAME] [BSP]"
    exit 1
fi

petalinux-create -t project -n $1 -s $2

exit 0