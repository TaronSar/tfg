
proc flash { } {
    set app_path "../cmake/build/"
    set app_file [glob -nocomplain -directory $app_path *.elf]

    if {[llength $app_file] != 1} {
        puts "ERROR: Multiple binary files at $app_path"
        exit
    }

    connect -url tcp:127.0.0.1:3121
    source "./tcl/zynqmp_utils.tcl"
    targets -set -nocase -filter {name =~"APU*"}
    rst -system
    after 3000
    targets -set -nocase -filter {name =~"PS TAP"}
    fpga -file "../../platform/hw/sdt/design_1_wrapper.bit"
    targets -set -nocase -filter {name =~"APU*"}
    loadhw -hw "../../platform/hw/design_1_wrapper.xsa" -mem-ranges [list {0x80000000 0xbfffffff} {0x400000000 0x5ffffffff} {0x1000000000 0x7fffffffff}] -regs
    configparams force-mem-access 1
    targets -set -nocase -filter {name =~"APU*"}
    set mode [expr [mrd -value 0xFF5E0200] & 0xf]
    targets -set -nocase -filter {name =~ "*A53*#0"}
    rst -processor
    dow "../../platform/export/platform/sw/boot/fsbl.elf"
    set bp_20_2_fsbl_bp [bpadd -addr &XFsbl_Exit]
    con -block -timeout 60
    bpremove $bp_20_2_fsbl_bp
    targets -set -nocase -filter {name =~ "*A53*#0"}
    rst -processor
    dow $app_file
    configparams force-mem-access 0
}