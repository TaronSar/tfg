proc boot_jtag { } {
############################
# Switch to JTAG boot mode #
############################
targets -set -filter {name =~ "PSU"}
# update multiboot to ZERO
mwr 0xffca0010 0x0
# change boot mode to JTAG
mwr 0xff5e0200 0x0100
# reset
rst -system
}

proc flash { } {

    set bitstream_path "../../platform/hw/"
    set bitstream_file [glob -nocomplain -directory $bitstream_path *.bit]

    if {[llength $bitstream_file] != 1} {
        puts "ERROR: Multiple bitstream files at $bitstream_path"
        exit
    }
    
    set app_path "../cmake/build/"
    set app_file [glob -nocomplain -directory $app_path *.elf]

    if {[llength $app_file] != 1} {
        puts "ERROR: Multiple binary files at $app_path"
        exit
    }

    connect
    boot_jtag
    
    after 2000
    targets -set -filter {name =~ "PL"}
    fpga $bitstream_file
    
    # Download pmufw.elf
    targets -set -filter {name =~ "PSU"}
    mwr 0xffca0038 0x1FF
    after 500
    targets -set -filter {name =~ "MicroBlaze PMU"}
    dow "../../platform/export/platform/sw/platform/boot/pmufw.elf"
    con
    after 500
    
    # Select A53 Core 0
    targets -set -filter {name =~ "Cortex-A53 #0"}
    rst -processor -clear-registers
    dow "../../platform/export/platform/sw/platform/boot/fsbl.elf"
    con
    after 10000
    stop
    
    dow $app_file
    

}
