#!/bin/bash

if [ ! -x "$(which petalinux-create)" ]; then
    echo "Petalinux tools not found"
    exit 1
fi

if [ $# -lt 2 ]; then
    echo "USAGE: $0 [PROJECT DIR] [XSA DIR]"
    exit 1
fi

cd $1
petalinux-config --get-hw-description $2
petalinux-config -c kernel
petalinux-config -c rootfs

exit 0
