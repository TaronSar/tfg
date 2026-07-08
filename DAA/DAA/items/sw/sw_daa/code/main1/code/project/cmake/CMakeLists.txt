cmake_minimum_required(VERSION 3.0.2)
project(daa)

if(NOT CROSS_ENV_PATH)
    message(STATUS "Cross enviroment path not set (CROSS_ENV_PATH variable).")
endif()

add_compile_options(-std=c++17)

SET(DAA_DIR         ${PROJECT_SOURCE_DIR}/../../../../../code)
SET(ITEMS_DIR       ${PROJECT_SOURCE_DIR}/../../../../../items)
SET(PERCEPTION_DIR  ${ITEMS_DIR}/_sw_perception)
SET(VLIBS_DIR       ${PERCEPTION_DIR}/items/Vlibs)

SET(DAA_INC         ${DAA_DIR}/include)
SET(DAA_SRC         ${DAA_DIR}/source)
SET(GNSSDENIED_DIR  ${PERCEPTION_DIR}/items/sw_gnssdenied)
SET(SOPHUS_DIR      ${GNSSDENIED_DIR}/items/sw_sophus)
SET(G2O_DIR         ${GNSSDENIED_DIR}/items/sw_g2o)
SET(ORB_SLAM3_DIR   ${GNSSDENIED_DIR}/items/sw_orbslam)
SET(DBOW_DIR        ${GNSSDENIED_DIR}/items/sw_dbow)
SET(WVLIBS_DIR      ${GNSSDENIED_DIR}/items/sw_wvlibs/code)

SET(LIB_COPROC_DIR  ${PERCEPTION_DIR}/items/sw_orb/items/sw_liborb_coproc/code)
SET(RTSP_DIR        ${PERCEPTION_DIR}/items/sw_rtsp/code)
SET(SMOLRTSP_DIR    ${PERCEPTION_DIR}/items/sw_rtsp/items/sw_smolrtsp)
SET(SW_RTSP_LIB_DIR ${RTSP_DIR}/project/cmake/build)

find_package(Eigen3 3.1.0 REQUIRED)

set(CMAKE_VERBOSE_MAKEFILE ON)
# set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall  -g3 ")
# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -g3 ")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall  -O3")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -O3")

SET(WITH_OPENCV ON)
if(WITH_OPENCV)
    find_package(OpenCV 4.4 REQUIRED PATHS ${CROSS_ENV_PATH}/lib64/cmake/opencv4)
    SET(OPENCV4_INCLUDE  ${OpenCV_INCLUDE_DIRS})
    SET(OPENCV4_LIB  ${OpenCV_LIBS})
endif()

set(DAA_LIBS "")
set(DAA_DEPS_INC "")
set(X264_SEARCH_PATHS "")
if (CMAKE_DAA_TEXAS EQUAL 1)
    set(TI_TARGETFS_DIR "/ti_targetfs")
    list (APPEND DAA_LIBS ${TI_TARGETFS_DIR}/lib/libonnxruntime.so)
    list (APPEND DAA_LIBS ${TI_TARGETFS_DIR}/lib/libtidl_onnxrt_EP.so)
    list (APPEND DAA_LIBS ${TI_TARGETFS_DIR}/lib/libvx_tidl_rt.so)
    set(ONNXRUNTIME_ROOT "/ti_targetfs/usr/include/onnxruntime")
    list (APPEND DAA_DEPS_INC
        "${ONNXRUNTIME_ROOT}/onnxruntime/include"
        "${ONNXRUNTIME_ROOT}/include/onnxruntime/core"
        "${ONNXRUNTIME_ROOT}/include/onnxruntime/core/session")
    list (APPEND X264_SEARCH_PATHS
        "${TI_TARGETFS_DIR}/usr/lib"
        "${TI_TARGETFS_DIR}/lib"
        "/usr/lib/aarch64-linux-gnu")
elseif (CMAKE_DAA_TEXAS EQUAL 0)
    if (CMAKE_CUDA_12 EQUAL 1)
        list (APPEND DAA_LIBS ${CROSS_ENV_PATH}/onnxruntime-1.18/lib/libonnxruntime.so)
        list (APPEND DAA_DEPS_INC
            "${CROSS_ENV_PATH}/onnxruntime-1.18/include")
    elseif(NOT DEFINED CMAKE_CUDA_12 OR CMAKE_CUDA_12 STREQUAL "" OR CMAKE_CUDA_12 EQUAL 0)
        list (APPEND DAA_LIBS ${CROSS_ENV_PATH}/onnxruntime-1.16/lib/libonnxruntime.so)
        list (APPEND DAA_DEPS_INC
            "${CROSS_ENV_PATH}/onnxruntime-1.16/include")
    endif()
    list (APPEND X264_SEARCH_PATHS
        "/usr/lib/aarch64-linux-gnu"
        "${CROSS_ENV_PATH}/lib"
        "${CROSS_ENV_PATH}/lib64")
endif()

find_library(X264_LIB
    NAMES x264
    PATHS ${X264_SEARCH_PATHS}
    NO_DEFAULT_PATH)

if (NOT X264_LIB)
    message(FATAL_ERROR "x264 library not found. Checked paths: ${X264_SEARCH_PATHS}")
endif()

add_library(rtsp_server_lib STATIC IMPORTED)
set_target_properties(rtsp_server_lib PROPERTIES
    IMPORTED_LOCATION ${SW_RTSP_LIB_DIR}/librtsp.a
)

include_directories(
    ${WVLIBS_DIR}/include
    ${PERCEPTION_DIR}/code/include
    ${VLIBS_DIR}/geomodel/code/include
    ${VLIBS_DIR}/base/code/include
    ${VLIBS_DIR}/first/code/include
    ${VLIBS_DIR}/ti/code/dsp/FPU/c28/include
    ${VLIBS_DIR}/maverick/code/include_SIL
    ${VLIBS_DIR}/maverick/code/include
    ${VLIBS_DIR}/bsp/code/include_SIL
    ${VLIBS_DIR}/bsp/code/include
    ${DAA_INC}
    ${DAA_SRC}
    ${SOPHUS_DIR}
    ${EIGEN3_INCLUDE_DIR}
    PUBLIC ${OPENCV4_INCLUDE}
    ${LIB_COPROC_DIR}/streaming/
    ${LIB_COPROC_DIR}/wrapper/

    ${RTSP_DIR}/include

    ${DAA_DEPS_INC}
    ${ONNXRUNTIME_INC_ROOT}
)

SET (MYLIB -Wl,--whole-archive ${VLIBS_DIR}/first/code/project/cmake/build/libfirst.a -Wl,--no-whole-archive)

# Set RTSP libraries (librería autocontenida + libevent core)
set(RTSP_LIBS
    rtsp_server_lib  # Librería autocontenida (incluye smolrtsp, smolrtsp-libevent, slice99, etc.)
    ${SW_RTSP_LIB_DIR}/_deps/libevent-build/lib/libevent_core.a  # Core libevent functions needed by smolrtsp-libevent
    pthread          # Threading support
    ${X264_LIB}      # H264 encoding
)

add_executable(${PROJECT_NAME} ${DAA_DIR}/${SRC_MAIN})

target_link_options(${PROJECT_NAME} PRIVATE
  -Wl,-rpath,/usr/lib
  -Wl,-rpath,/usr/lib64
  -Wl,-rpath-link,${TI_TARGETFS_DIR}/usr/lib
  -Wl,-rpath-link,${TI_TARGETFS_DIR}/lib
  -Wl,-rpath-link,/home/root/targetfs/usr/lib/
)

target_link_libraries(${PROJECT_NAME}
    pthread
    -Wl,--start-group
    ${WVLIBS_DIR}/project/cmake/build/libwvlibs.a
    ${VLIBS_DIR}/bsp/code/project/cmake/build/libbsp.a
    ${PERCEPTION_DIR}/code/project/cmake/build/libsw_perception.a
    ${LIB_COPROC_DIR}/project/cmake/build/liborb_coproc.a
    ${LIB_COPROC_DIR}/build/streaming/libstreaming.a
    ${OPENCV4_LIB}
    ${EIGEN3_LIBS}
    ${DAA_LIBS}
    ${RTSP_LIBS}
    -Wl,--end-group
)