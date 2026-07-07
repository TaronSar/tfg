cmake_minimum_required(VERSION 3.0.2)
project(hil)


set(CMAKE_VERBOSE_MAKEFILE ON)

find_package(OpenCV 4.4 REQUIRED PATHS ${CROSS_ENV_PATH}/lib64/cmake/opencv4)
SET(OPENCV4_INCLUDE  ${OpenCV_INCLUDE_DIRS})
SET(OPENCV4_LIB  ${OpenCV_LIBS})

## System dependencies are found with CMake's conventions
# find_package(Boost REQUIRED COMPONENTS system)

###########
## Build ##
###########
#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wl,--no-as-needed")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3 -DVERBOSE")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -std=c++17 -DVERBOSE -pthread")


#if(VIDEO_STREAMING)
#  set(STREAMING_DIR "${DEPS_PATH}/../streaming/")
#  set(STREAMING_LIBS "${DEPS_PATH}/../streaming/libstreaming.so")
#endif()

## Specify additional locations of header files
## Your package locations should be listed before other locations
#SET(ORB_SLAM3_DIR ../../../ORB_SLAM3)
#SET(ORB_SLAM3_DIR ${PROJECT_SOURCE_DIR})
#SET(VLIBS_DIR      /workspace/Vlibs)
SET(LIB_COPROC_DIR ${PROJECT_SOURCE_DIR}/../../../../sw_orb/items/sw_liborb_coproc/code)
SET(WVLIBS_DIR ${PROJECT_SOURCE_DIR}/../../../../sw_gnssdenied/items/sw_wvlibs)
SET(HIL_DIR ${PROJECT_SOURCE_DIR}/../../)
SET(VLIBS_DIR      ${PROJECT_SOURCE_DIR}/../../../../Vlibs)

include_directories(
${VLIBS_DIR}/base/code/include
${LIB_COPROC_DIR}/include/
)

add_definitions(-DREGISTER_TIMES)

set(THREADS_PREFER_PTHREAD_FLAG ON)

file(GLOB SOURCE_FILES

    "${LIB_COPROC_DIR}/source/*.c"
    "${PROJECT_SOURCE_DIR}/../../source/*.cpp"
)

include_directories(
    ${PROJECT_SOURCE_DIR}/../../include
PRIVATE ${WVLIBS_DIR}/code/include
${VLIBS_DIR}/geomodel/code/include
${VLIBS_DIR}/base/code/include
${VLIBS_DIR}/first/code/include
${VLIBS_DIR}/ti/code/dsp/FPU/c28/include
${VLIBS_DIR}/maverick/code/include_SIL
${VLIBS_DIR}/maverick/code/include
${VLIBS_DIR}/bsp/code/include_SIL
${VLIBS_DIR}/bsp/code/include
${VLIBS_DIR}/media/code/include
${VLIBS_DIR}/devices/code/include
${VLIBS_DIR}/DFS2/code/include
${VLIBS_DIR}/DSP28x/code/include
${VLIBS_DIR}/stanag/code/include
PUBLIC ${OPENCV4_INCLUDE}
)

add_executable(${PROJECT_NAME} ${SOURCE_FILES})

MESSAGE(STATUS ${WVLIBS_DIR})

target_link_libraries(${PROJECT_NAME}
    ${OpenCV_LIBS}
   ${WVLIBS_DIR}/code/project/cmake/build/libwvlibs.a
)