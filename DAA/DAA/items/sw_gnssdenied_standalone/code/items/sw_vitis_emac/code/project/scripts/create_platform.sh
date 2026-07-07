#!/bin/bash

if [ -z "$1" ]; then
    echo "USAGE: $0 [XSA FILE]"
else
    echo "Creating platform from: $1"
    vitis -s py/create_platform.py $1
fi