
cmake_minimum_required(VERSION 3.0.2)
project(zusp)

set(CMAKE_VERBOSE_MAKEFILE ON)
set(CMAKE_C_COMPILER ${CCPREFIX}gcc)
set(CMAKE_CXX_COMPILER ${CCPREFIX}g++)


enable_language(ASM)
###########
## Build ##
###########
#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wl,--no-as-needed")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -std=gnu++03 -Wall -O0 -g3 -fmessage-length=0 -march=armv8-a -DARMA53_64 -Os -flto -ffat-lto-objects")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -std=gnu++03  -Wall -O0 -g3 -fmessage-length=0 -march=armv8-a -DARMA53_64 -Os -flto -ffat-lto-objects")

SET(VLIBS_DIR     ${PROJECT_SOURCE_DIR}/../../../../Vlibs)

if(NEON)
    message(STATUS "Added NEON support\n")
    add_compile_definitions(NEON)
endif()

include_directories(
    "${PROJECT_SOURCE_DIR}/../../include/"
    "${PROJECT_SOURCE_DIR}/../../include/CortexA53/"
    "${VLIBS_DIR}/bsp/code/include"
)

file(GLOB SOURCE_FILES
    "${PROJECT_SOURCE_DIR}/../../source/*.cpp"
    "${PROJECT_SOURCE_DIR}/../../source/CortexA53/*.cpp"
    "${PROJECT_SOURCE_DIR}/../../source/CortexA53/*.S"
    "${PROJECT_SOURCE_DIR}/../../source/Boot/*.c"
    "${PROJECT_SOURCE_DIR}/../../source/Boot/*.S"
)

add_library(${PROJECT_NAME} STATIC ${SOURCE_FILES})

set_target_properties(${PROJECT_NAME} PROPERTIES
    ARCHIVE_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/../../lib
    LIBRARY_OUTPUT_DIRECTORY ${PROJECT_SOURCE_DIR}/../../lib
)

MESSAGE(STATUS ${PROJECT_SOURCE_DIR})

string(REPLACE "-rdynamic" "" CMAKE_SHARED_LIBRARY_LINK_C_FLAGS "${CMAKE_SHARED_LIBRARY_LINK_C_FLAGS}")
string(REPLACE "-rdynamic" "" CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS "${CMAKE_SHARED_LIBRARY_LINK_CXX_FLAGS}")