cmake_minimum_required(VERSION 3.0.2)
project(lm)

if(NOT CROSS_ENV_PATH)
    message(STATUS "Cross enviroment path not set (CROSS_ENV_PATH variable).")
endif()

add_compile_options(-std=c++17)

SET(LM_DIR          ${PROJECT_SOURCE_DIR}/../../../../../code)
SET(ITEMS_DIR       ${PROJECT_SOURCE_DIR}/../../../../../items)
SET(PERCEPTION_DIR  ${ITEMS_DIR}/_sw_perception)
SET(VLIBS_DIR       ${PERCEPTION_DIR}/items/Vlibs)

SET(GNSSDENIED_DIR  ${PERCEPTION_DIR}/items/sw_gnssdenied)
SET(SOPHUS_DIR      ${GNSSDENIED_DIR}/items/sw_sophus)
SET(G2O_DIR         ${GNSSDENIED_DIR}/items/sw_g2o)
SET(ORB_SLAM3_DIR   ${GNSSDENIED_DIR}/items/sw_orbslam)
SET(DBOW_DIR        ${GNSSDENIED_DIR}/items/sw_dbow)
SET(G2O_DIR         ${GNSSDENIED_DIR}/items/sw_g2o)
SET(WVLIBS_DIR      ${GNSSDENIED_DIR}/items/sw_wvlibs/code)

MESSAGE (STATUS "WVLIBS_DIR: ${WVLIBS_DIR}")

SET(LIB_COPROC_DIR  ${PERCEPTION_DIR}/items/sw_orb/items/sw_liborb_coproc/code)
SET(MAVLINK_DIR     ${PERCEPTION_DIR}/items/sw_mavlink/code)
SET(RTSP_DIR        ${PERCEPTION_DIR}/items/sw_rtsp/code)
SET(SMOLRTSP_DIR    ${PERCEPTION_DIR}/items/sw_rtsp/items/sw_smolrtsp)
SET(SW_RTSP_LIB_DIR ${RTSP_DIR}/project/cmake/build)
find_package(Eigen3 3.1.0 REQUIRED)

set(CMAKE_VERBOSE_MAKEFILE ON)
# set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall  -g3 ")
# set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -g3 ")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall  -O3 -fno-short-enums")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall -O3 -fno-short-enums")

SET(WITH_OPENCV ON)
if(WITH_OPENCV)
    find_package(OpenCV 4.4 REQUIRED PATHS ${CROSS_ENV_PATH}/lib64/cmake/opencv4)
    SET(OPENCV4_INCLUDE  ${OpenCV_INCLUDE_DIRS})
    SET(OPENCV4_LIB  ${OpenCV_LIBS})
endif()

SET(AI_DEPS_LIB "")
SET(AI_DEPS_INCLUDE "")
if (CMAKE_DAA_TEXAS EQUAL 1)
    set(TI_TARGETFS_DIR "/ti_targetfs")
    list (APPEND AI_DEPS_LIB ${TI_TARGETFS_DIR}/lib/libonnxruntime.so)
    list (APPEND AI_DEPS_LIB ${TI_TARGETFS_DIR}/lib/libtidl_onnxrt_EP.so)
    list (APPEND AI_DEPS_LIB ${TI_TARGETFS_DIR}/lib/libvx_tidl_rt.so)
    set(ONNXRUNTIME_ROOT "/ti_targetfs/usr/include/onnxruntime")
    list (APPEND AI_DEPS_INCLUDE
        "${ONNXRUNTIME_ROOT}/onnxruntime/include"
        "${ONNXRUNTIME_ROOT}/include/onnxruntime/core"
        "${ONNXRUNTIME_ROOT}/include/onnxruntime/core/session")
    # list (APPEND X264_SEARCH_PATHS
    #     "${TI_TARGETFS_DIR}/usr/lib"
    #     "${TI_TARGETFS_DIR}/lib"
    #     "/usr/lib/aarch64-linux-gnu")
elseif (CMAKE_DAA_TEXAS EQUAL 0)
    if (CMAKE_CUDA_12 EQUAL 1)
        list (APPEND AI_DEPS_LIB ${CROSS_ENV_PATH}/onnxruntime-1.18/lib/libonnxruntime.so)
        list (APPEND AI_DEPS_INCLUDE
            "${CROSS_ENV_PATH}/onnxruntime-1.18/include")
    elseif(NOT DEFINED CMAKE_CUDA_12 OR CMAKE_CUDA_12 STREQUAL "" OR CMAKE_CUDA_12 EQUAL 0)
        list (APPEND AI_DEPS_LIB ${CROSS_ENV_PATH}/onnxruntime-1.16/lib/libonnxruntime.so)
        list (APPEND AI_DEPS_INCLUDE
            "${CROSS_ENV_PATH}/onnxruntime-1.16/include")
    endif()
    # list (APPEND X264_SEARCH_PATHS
    #     "/usr/lib/aarch64-linux-gnu"
    #     "${CROSS_ENV_PATH}/lib"
    #     "${CROSS_ENV_PATH}/lib64")
endif()

# Create imported target for rtsp_server library
add_library(rtsp_server_lib STATIC IMPORTED)
set_target_properties(rtsp_server_lib PROPERTIES
    IMPORTED_LOCATION ${SW_RTSP_LIB_DIR}/librtsp.a
)

include_directories(
    ${WVLIBS_DIR}/include
    ${PERCEPTION_DIR}/code/include
    ${VLIBS_DIR}/bsp/code/include/nano
    ${VLIBS_DIR}/bsp/code/include
    ${VLIBS_DIR}/base/code/include
    ${VLIBS_DIR}/first/code/include
    ${VLIBS_DIR}/maverick/code/include
    ${VLIBS_DIR}/hal/code/include
    ${VLIBS_DIR}/geomodel/code/include
    ${VLIBS_DIR}/stanag/code/include
    ${VLIBS_DIR}/IP_Stack/code/include
    ${SOPHUS_DIR}
    ${EIGEN3_INCLUDE_DIR}
    PUBLIC ${OPENCV4_INCLUDE}
    ${LIB_COPROC_DIR}/streaming/
    ${LIB_COPROC_DIR}/wrapper/
    ${MAVLINK_DIR}/include
    ${RTSP_DIR}/include
    ${AI_DEPS_INCLUDE}

    ${ORB_SLAM3_DIR}
    PRIVATE ${DBOW_DIR}
    PRIVATE ${SOPHUS_DIR}
    PRIVATE ${G2O_DIR}
    PRIVATE ${ORB_SLAM3_DIR}/include
    PRIVATE ${ORB_SLAM3_DIR}/include/CameraModels
    PRIVATE ${G2O_DIR}/g2o/core
)

SET (MYLIB -Wl,--whole-archive ${VLIBS_DIR}/first/code/project/cmake/build/libfirst.a -Wl,--no-whole-archive)

if(NOT DEFINED CROSS_ENV_PATH OR CROSS_ENV_PATH STREQUAL "" OR CROSS_ENV_PATH EQUAL 0)
  SET(LIBBOOST -lboost_serialization)
else()
  include_directories( ${CROSS_ENV_PATH}/lib_boost/include)

  SET(LIBBOOST ${CROSS_ENV_PATH}/lib/libboost_serialization.a)
endif()


# Set RTSP libraries (librería autocontenida + libevent core)
set(RTSP_LIBS
    rtsp_server_lib  # Librería autocontenida (incluye smolrtsp, smolrtsp-libevent, slice99, etc.)
    ${SW_RTSP_LIB_DIR}/_deps/libevent-build/lib/libevent_core.a  # Core libevent functions needed by smolrtsp-libevent
    pthread          # Threading support
    x264             # H264 encoding
)

add_executable(${PROJECT_NAME} ${LM_DIR}/${SRC_MAIN})

target_link_options(${PROJECT_NAME} PRIVATE
    -Wl,-rpath,/usr/lib
    -Wl,-rpath,/usr/lib64
)

target_link_libraries(${PROJECT_NAME}
    pthread
    -Wl,--start-group
    ${WVLIBS_DIR}/project/cmake/build/libwvlibs.a
    ${VLIBS_DIR}/bsp/code/project/cmake/build/libbsp.a
    ${ORB_SLAM3_DIR}/lib/libORB_SLAM3.a
    ${G2O_DIR}/lib/libg2o.a
    ${DBOW_DIR}/lib/libDBoW2.a
    ${PERCEPTION_DIR}/code/project/cmake/build/libsw_perception.a
    ${LIBBOOST}
    ${LIB_COPROC_DIR}/project/cmake/build/liborb_coproc.a
    ${LIB_COPROC_DIR}/build/streaming/libstreaming.a
    # ${SMOLRTSP_DIR}/lib/libsmolrtsp.a
    ${OPENCV4_LIB}
    ${EIGEN3_LIBS}
    # /usr/lib/aarch64-linux-gnu/libx264.so.163
    ${RTSP_LIBS}
    ${AI_DEPS_LIB}
    -Wl,--end-group
)
