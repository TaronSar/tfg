#!/bin/bash

xsdb -interactive -eval "source tcl/flash.tcl; flash; con; exit"
