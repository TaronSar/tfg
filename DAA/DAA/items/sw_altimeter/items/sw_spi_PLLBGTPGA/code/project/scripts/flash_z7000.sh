#!/bin/bash

xsdb -interactive -eval "source ../../platform/hw/ps7_init.tcl; source flash_ALINX.tcl; flash"
