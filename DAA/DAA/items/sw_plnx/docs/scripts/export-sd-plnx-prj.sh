#!/bin/bash

if [ ! -x "$(which petalinux-create)" ]; then
    echo "Petalinux tools not found"
    exit 1
fi

if [ $# -lt 2 ]; then
    echo "USAGE: $0 [PROJECT DIR] [SD DIR]"
    exit 1
fi

cd $1/images/linux
cp boot.scr BOOT.BIN image.ub $2
echo "SD prepared successfully"
exit 0
