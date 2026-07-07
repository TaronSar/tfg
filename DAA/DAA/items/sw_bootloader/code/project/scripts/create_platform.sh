#!/bin/bash

if [ -z "$1" ]; then
    echo "USAGE: $0 [XSA FILE]"
else
    echo "Creating platform from: $1 for psu_cortexa53_0, named: platform"
    xsct -eval "source tcl/platform.tcl; create_platform $1 platform psu_cortexa53_0"
fi