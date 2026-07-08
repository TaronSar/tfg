cmake_minimum_required(VERSION 3.0.2)
project(sw_colibri)

# include(/usr/lib/aarch64-linux-gnu/cmake/opencv4/OpenCVConfig.cmake)
# include(/usr/lib/aarch64-linux-gnu/cmake/opencv4/OpenCVConfig-version.cmake)
# include(/usr/lib/aarch64-linux-gnu/cmake/opencv4/OpenCVModules.cmake)
# include(/usr/lib/aarch64-linux-gnu/cmake/opencv4/OpenCVModules-release.cmake)

SET(VLIBS_DIR      ${PROJECT_SOURCE_DIR}/../../../../../items/Vlibs)
SET(VPROTO_DIR ${PROJECT_SOURCE_DIR}/../../../../sw_vproto/code)
SET(VPROTO_SRC ${PROJECT_SOURCE_DIR}/../../../../sw_vproto/code/source)
SET(VPROTO_INC ${PROJECT_SOURCE_DIR}/../../../../sw_vproto/code/include)
SET(COLIBRI_INC ${PROJECT_SOURCE_DIR}/../../../../sw_colibri/code/include)
SET(COLIBRI_SRC ${PROJECT_SOURCE_DIR}/../../../../sw_colibri/code/source)
SET(ITEMS_DIR ${PROJECT_SOURCE_DIR}/../../../../../items/)
SET(SOPHUS_DIR ${ITEMS_DIR}/sw_gnssdenied/items/sw_sophus)
SET(G2O_DIR ${ITEMS_DIR}/sw_gnssdenied/items/sw_g2o)
SET(WVLIBS_DIR     ${PROJECT_SOURCE_DIR}/../../../../sw_gnssdenied/items/sw_wvlibs/code)

set(THREADS_PREFER_PTHREAD_FLAG ON)
set(CMAKE_POSITION_INDEPENDENT_CODE ON)

find_package(Eigen3 3.1.0 REQUIRED)

set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS}  -Wall   -g3")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wall   -g3")


SET(OpenCV_paths "")
list (APPEND OpenCV_paths "/usr/lib/aarch64-linux-gnu/cmake/opencv4")

SET(WITH_OPENCV ON)
if(WITH_OPENCV)
    find_package(OpenCV 4.2 REQUIRED PATHS ${OpenCV_paths} NO_DEFAULT_PATH)
    SET(OPENCV4_INCLUDE  ${OpenCV_INCLUDE_DIRS})
    SET(OPENCV4_LIB  ${OpenCV_LIBS})
endif()

include_directories(
    ${VPROTO_INC}
    ${VLIBS_DIR}/first/code/include
    ${VLIBS_DIR}/base/code/include
    ${VLIBS_DIR}/bsp/code/include
    ${VLIBS_DIR}/ti/code/dsp/FPU/c28/include
    ${COLIBRI_INC}
    ${OPENCV4_INCLUDE}  
    ${EIGEN3_INCLUDE_DIR} 
    ${G2O_DIR}
    ${SOPHUS_DIR}
    ${WVLIBS_DIR}/include
)

add_library(${PROJECT_NAME} SHARED
    ${COLIBRI_SRC}/Location_cv.cpp
    ${VPROTO_DIR}/project/cmake/build/libsw_vproto.a
)

target_link_libraries(${PROJECT_NAME}
    ${VPROTO_DIR}/project/cmake/build/libsw_vproto.a
    ${WVLIBS_DIR}/project/cmake/build/libwvlibs.a
    ${OPENCV4_LIB}
    # ${OPENCV4_LIB}/libopencv_aruco.so
    # ${OPENCV4_LIB}/libopencv_highgui.so
)