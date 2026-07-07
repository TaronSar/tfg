#/******************************************************************************
#*
#* (c) Copyright 2010-2020 Xilinx, Inc. All rights reserved.
#*
#* This file contains confidential and proprietary information of Xilinx, Inc.
#* and is protected under U.S. and international copyright and other
#* intellectual property laws.
#*
#* DISCLAIMER
#* This disclaimer is not a license and does not grant any rights to the
#* materials distributed herewith. Except as otherwise provided in a valid
#* license issued to you by Xilinx, and to the maximum extent permitted by
#* applicable law: (1) THESE MATERIALS ARE MADE AVAILABLE "AS IS" AND WITH ALL
#* FAULTS, AND XILINX HEREBY DISCLAIMS ALL WARRANTIES AND CONDITIONS, EXPRESS,
#* IMPLIED, OR STATUTORY, INCLUDING BUT NOT LIMITED TO WARRANTIES OF
#* MERCHANTABILITY, NON-INFRINGEMENT, OR FITNESS FOR ANY PARTICULAR PURPOSE;
#* and (2) Xilinx shall not be liable (whether in contract or tort, including
#* negligence, or under any other theory of liability) for any loss or damage
#* of any kind or nature related to, arising under or in connection with these
#* materials, including for any direct, or any indirect, special, incidental,
#* or consequential loss or damage (including loss of data, profits, goodwill,
#* or any type of loss or damage suffered as a result of any action brought by
#* a third party) even if such damage or loss was reasonably foreseeable or
#* Xilinx had been advised of the possibility of the same.
#*
#* CRITICAL APPLICATIONS
#* Xilinx products are not designed or intended to be fail-safe, or for use in
#* any application requiring fail-safe performance, such as life-support or
#* safety devices or systems, Class III medical devices, nuclear facilities,
#* applications related to the deployment of airbags, or any other applications
#* that could lead to death, personal injury, or severe property or
#* environmental damage (individually and collectively, "Critical
#* Applications"). Customer assumes the sole risk and liability of any use of
#* Xilinx products in Critical Applications, subject only to applicable laws
#* and regulations governing limitations on product liability.
#*
#* THIS COPYRIGHT NOTICE AND DISCLAIMER MUST BE RETAINED AS PART OF THIS FILE
#* AT ALL TIMES.
#*
#******************************************************************************/

###DDR remap initialization
proc ddrremap {} {

    puts "Info:  Remapping DDR memory to 0x0"

    mwr 0xF8F00000 0x0 ;
    mwr 0xF8F00040 0x0 ;
    mwr 0xF8F00000 0x2 ;
}

###RAM remap initialization
proc ramremap {} {

    puts "Info:  Remapping 256k of RAM memory to 0xFFFC0000"

    # unlock SLCR
    mwr 0xF8000008 0xDF0D

    # Remap all four 64k blocks to a high address starting at 0xfffc0000
    mwr 0xF8000910 0x1FF;

    # lock SLCR
    mwr 0xF8000004 0x767B
}

###User fabric port reset initialization
proc init_user {} {

    puts "Note:: init_user command is Deprecated. Use ps7_post_config from ps7_init.tcl"

    # unlock SLCR
    mwr 0xF8000008 0xDF0D

    # enable level shifters
    mwr 0xF8000900 0xF

    # clear resets on AXI fabric ports
    mwr 0xF8000240 0x01F33F0F
    mwr 0xF8000240 0x0

    # lock SLCR
    mwr 0xF8000004 0x767B
}

namespace eval zynq {
    proc get_pl_ranges {} {
        return [list {0x40000000 0xbfffffff}]
    }
}