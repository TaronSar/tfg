
cmake_minimum_required(VERSION 3.0.2)
project(helloworld)


set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_C_COMPILER ${CCPREFIX}gcc)
set(CMAKE_CXX_COMPILER ${CCPREFIX}g++)
set(CMAKE_LINKER ${CCPREFIX}ld)
set(USER_LINKER_SCRIPT ${LDSCRIPT})
enable_language(ASM)
###########
## Build ##
###########
#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wl,--no-as-needed")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall -O0 -g3 -fmessage-length=0 ")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS}  -Wall -O0 -g3 -fmessage-length=0 ")

include_directories(
    ../../source/
    ../../platform/psu_cortexa53_0/domain_psu_cortexa53_0/bsp/psu_cortexa53_0/include
    #../../platform/export/platform/sw/platform/domain_psu_cortexa53_0/bspinclude/include

)

add_definitions(-DREGISTER_TIMES)

file(GLOB OBJECT_FILES 
    "../../platform/psu_cortexa53_0/domain_psu_cortexa53_0/bsp/psu_cortexa53_0/lib/*.o" 
    #"../../platform/export/platform/sw/platform/domain_psu_cortexa53_0/bsplib/lib/*.o"
    )

file(GLOB SOURCE_FILES
    "../../source/init_multicore.S"
    "../../source/helloworld.cpp"
    "../../source/platform.c"
)

add_executable(${PROJECT_NAME}.elf ${SOURCE_FILES} ${OBJECT_FILES})

target_include_directories(${PROJECT_NAME}.elf SYSTEM PRIVATE

)


target_link_libraries(${PROJECT_NAME}.elf
m
${PROJECT_SOURCE_DIR}/../../platform/psu_cortexa53_0/domain_psu_cortexa53_0/bsp/psu_cortexa53_0/lib/libxil.a
)

set_target_properties(${PROJECT_NAME}.elf PROPERTIES LINK_FLAGS "-Wl,-T -Wl,${USER_LINKER_SCRIPT}")
#target_link_options(${PROJECT_NAME}.elf PRIVATE -ffreestanding -e boot_start)
target_link_options(${PROJECT_NAME}.elf PRIVATE -ffreestanding)

string(REPLACE "-rdynamic" "" CMAKE_SHARED_LIBRARY_LINK_C_FLAGS "${CMAKE_SHARED_LIBRARY_LINK_C_FLAGS}")
string(REPLACE "-rdynamic" "" CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS "${CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS}")
