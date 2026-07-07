
cmake_minimum_required(VERSION 3.0.2)
project(helloworld)


set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_C_COMPILER ${CCPREFIX}gcc)
set(CMAKE_LINKER ${CCPREFIX}ld)
set(USER_LINKER_SCRIPT ${LDSCRIPT})

###########
## Build ##
###########
#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wl,--no-as-needed")

set(XILINX_SPEC  "${PROJECT_SOURCE_DIR}/../../platform/zynq_fsbl/Xilinx.spec") #TO CHECK

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -O2 -DSDT -MMD -MP -mcpu=cortex-a9 -mfpu=vfpv3 -mfloat-abi=hard  -Wall -Wextra -O0  -g3 -specs=${XILINX_SPEC} ")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -g -DSDT")

include_directories(
    ../../sources/
    ../../platform/ps7_cortexa9_0/domain_ps7_cortexa9_0/bsp/ps7_cortexa9_0/include
    #../../platform/export/platform/sw/platform/domain_psu_cortexa53_0/bspinclude/include
)

add_definitions(-DREGISTER_TIMES)

file(GLOB OBJECT_FILES 
    "../../platform/ps7_cortexa9_0/domain_ps7_cortexa9_0/bsp/ps7_cortexa9_0/lib/*.o" 
    #"../../platform/export/platform/sw/platform/domain_psu_cortexa53_0/bsplib/lib/*.o"
    )

file(GLOB SOURCE_FILES
    "../../sources/helloworld.c"
    "../../sources/platform.c"
    "../../sources/*.c"
)

add_executable(${PROJECT_NAME}.elf ${SOURCE_FILES} ${OBJECT_FILES})

target_include_directories(${PROJECT_NAME}.elf SYSTEM PRIVATE

)


target_link_libraries(${PROJECT_NAME}.elf
m
${PROJECT_SOURCE_DIR}/../../platform/ps7_cortexa9_0/domain_ps7_cortexa9_0/bsp/ps7_cortexa9_0/lib/libxil.a
)

set_target_properties(${PROJECT_NAME}.elf PROPERTIES LINK_FLAGS "-Wl,-T -Wl,${USER_LINKER_SCRIPT}")


#target_link_options(${PROJECT_NAME}.elf PRIVATE "-T${USER_LINKER_SCRIPT}")


string(REPLACE "-rdynamic" "" CMAKE_SHARED_LIBRARY_LINK_C_FLAGS "${CMAKE_SHARED_LIBRARY_LINK_C_FLAGS}")
