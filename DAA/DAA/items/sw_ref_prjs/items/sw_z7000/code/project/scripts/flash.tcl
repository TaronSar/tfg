
proc flash { } {

    connect 

    targets -set -filter {name =~ "xc7z*"}
    fpga "../../platform/hw/design_1_wrapper.bit"

    targets -set -filter {name =~ "ARM*#0"}
    ps7_init

    dow "../cmake/build/helloworld.elf"
    after 500
    con
}
