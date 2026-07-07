
cmake_minimum_required(VERSION 3.0.2)
project(${APP_NAME})

set(CMAKE_VERBOSE_MAKEFILE ON)

set(CMAKE_C_COMPILER ${CCPREFIX}gcc)
set(CMAKE_CXX_COMPILER ${CCPREFIX}g++)

set(USER_LINKER_SCRIPT ${LDSCRIPT})

enable_language(ASM)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -std=gnu++03 -Wall -O0 -g3 -fmessage-length=0 -mcpu=cortex-a53+simd -DARMA53_64 -Os -flto -ffat-lto-objects")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=gnu++03 -Wall -O0 -g3 -fmessage-length=0 -mcpu=cortex-a53+simd -DARMA53_64 -Os -flto -ffat-lto-objects")

SET(VLIBS_DIR ${PROJECT_SOURCE_DIR}/../../../../Vlibs)
# SET(WVLIBS_DIR ${PROJECT_SOURCE_DIR}/../../../../sw_gnssdenied/items/sw_wvlibs)

include_directories(
    "${PROJECT_SOURCE_DIR}/../../include/"
    "../../platform/psu_cortexa53_0/domain_psu_cortexa53_0/bsp/psu_cortexa53_0/include"
    "/opt/Xilinx/Vitis/2024.1/gnu/aarch64/lin/aarch64-none/x86_64-oesdk-linux/usr/lib/aarch64-xilinx-elf/gcc/aarch64-xilinx-elf/12.2.0/include/"

    ${VLIBS_DIR}/geomodel/code/include
    ${VLIBS_DIR}/base/code/include
    ${VLIBS_DIR}/first/code/include
    ${VLIBS_DIR}/ti/code/dsp/FPU/arm/include
    ${VLIBS_DIR}/maverick/code/include_SIL
    ${VLIBS_DIR}/maverick/code/include
    ${VLIBS_DIR}/bsp/code/include_SIL
    ${VLIBS_DIR}/bsp/code/include
    ${VLIBS_DIR}/media/code/include
    ${VLIBS_DIR}/devices/code/include
    ${VLIBS_DIR}/DFS2/code/include
    ${VLIBS_DIR}/DSP28x/code/include
    ${VLIBS_DIR}/stanag/code/include
    ${VLIBS_DIR}/vbootloader/code/include
)

file(GLOB SOURCE_FILES
    "../../source/*.c"
    "../../source/*.cpp"
    "../../source/*.S"
)


file(GLOB OBJECT_FILES 
    "${PROJECT_SOURCE_DIR}/../../platform/psu_cortexa53_0/domain_psu_cortexa53_0/bsp/psu_cortexa53_0/lib/*.o"
)

add_executable(${PROJECT_NAME}.elf ${SRC_MAIN} ${SOURCE_FILES} ${OBJECT_FILES})

target_include_directories(${PROJECT_NAME}.elf SYSTEM PRIVATE)

target_link_libraries(${PROJECT_NAME}.elf
    ${PROJECT_SOURCE_DIR}/../../platform/psu_cortexa53_0/domain_psu_cortexa53_0/bsp/psu_cortexa53_0/lib/libxil.a

    ${VLIBS_DIR}/lib/libbase.a
    ${VLIBS_DIR}/lib/libbsp.a
    ${VLIBS_DIR}/lib/libCfgmgr.a
    ${VLIBS_DIR}/lib/libDFS2.a
    ${VLIBS_DIR}/lib/libfirst.a
    ${VLIBS_DIR}/lib/libgeomodel.a
    ${VLIBS_DIR}/lib/libmaverick.a
    ${VLIBS_DIR}/lib/libstanag.a
    ${VLIBS_DIR}/lib/libUSDdrv.a
    
    # ${WVLIBS_DIR}/code/project/cmake/build/libwvlibs.a

    m
    c
    gcc
)

set_target_properties(${PROJECT_NAME}.elf PROPERTIES LINK_FLAGS "-Wl,-T -Wl,${USER_LINKER_SCRIPT}")
target_link_options(${PROJECT_NAME}.elf PRIVATE -ffreestanding)

message(STATUS ${CMAKE_SHARED_LIBRARY_LINK_C_FLAGS})

string(REPLACE "-rdynamic" "" CMAKE_SHARED_LIBRARY_LINK_C_FLAGS "-Wl,--start-group,-lxil,-lgcc,-lc,--end-group")
string(REPLACE "-rdynamic" "" CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS "${CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS}")
