cmake_minimum_required(VERSION 3.0.2)
project(orb_coproc)

add_compile_options(-std=c++17)

SET(PRJ_DIR      ${PROJECT_SOURCE_DIR}/../../)
SET(VLIBS_DIR      ${PROJECT_SOURCE_DIR}/../../../../../items/Vlibs)

set(THREADS_PREFER_PTHREAD_FLAG ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall  -g3 ${VERBOSE_FLAGS}")#-O3")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -g3 ${VERBOSE_FLAGS}")#  -O3")
# set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall  -O3")
# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -O3")

SET(WVLIBS_DIR ${PROJECT_SOURCE_DIR}/../../../../../../sw_wvlibs)
SET(VLIBS_DIR  ${PROJECT_SOURCE_DIR}/../../../../../../Vlibs)


file(GLOB DRIVERS_SOURCES 
  "${PRJ_DIR}/source/*.c"
  "${PRJ_DIR}/xilinx/bsp_psu_cortexa53/v_gamma_lut_v1_1/*.c"
  "${PRJ_DIR}/xilinx/bsp_psu_cortexa53/v_demosaic_v1_1/*.c"
)

file(GLOB WRAPPER_SOURCES 
  "${PRJ_DIR}/wrapper/*.cpp"
)


set(CMAKE_VERBOSE_MAKEFILE ON)

include_directories(
  ${PRJ_DIR}/include
  ${PRJ_DIR}/wrapper
  ${PRJ_DIR}/xilinx/bsp_psu_cortexa53
  ${PRJ_DIR}/xilinx/bsp_psu_cortexa53/v_demosaic_v1_1
  ${PRJ_DIR}/xilinx/bsp_psu_cortexa53/v_gamma_lut_v1_1

)


MESSAGE(STATUS ${LIB_COPROC_DIR})

add_library(${PROJECT_NAME}  ${DRIVERS_SOURCES} ${WRAPPER_SOURCES}
)

target_link_libraries(${PROJECT_NAME}
    #${WVLIBS_DIR}/project/cmake/build/libwvlibs.a
    )
