#!/bin/bash

if [ ! -x "$(which petalinux-create)" ]; then
    echo "Petalinux tools not found"
    exit 1
fi

if [ $# -lt 1 ]; then
    echo "USAGE: $0 [PROJECT DIR]"
    exit 1
fi

cd $1
petalinux-package --boot --force --fsbl images/linux/zynqmp_fsbl.elf --fpga images/linux/system.bit --u-boot

exit 0
