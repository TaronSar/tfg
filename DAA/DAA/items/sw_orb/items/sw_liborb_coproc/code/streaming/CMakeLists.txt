
cmake_minimum_required(VERSION 3.12)

project(streaming)

SET(PROJ_DIR ${PROJECT_SOURCE_DIR}/../streaming/)
SET(WVLIBS_DIR     ${PROJECT_SOURCE_DIR}/../../../../../sw_gnssdenied/items/sw_wvlibs/code)
SET(VLIBS_DIR      ${PROJECT_SOURCE_DIR}/../../../../../Vlibs)

LIST(APPEND CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake_modules)

#find_package(OpenCV 4.4)
MESSAGE(STATUS ${CROSS_ENV_PATH}/lib64/cmake/opencv4)
find_package(OpenCV 4.4 REQUIRED PATHS ${CROSS_ENV_PATH}/lib64/cmake/opencv4)
#find_package(OpenCV 4.4 REQUIRED PATHS ${OpenCV_PATH})

include_directories(
    ${VLIBS_DIR}/bsp/code/include
    ${VLIBS_DIR}/first/code/include
    ${VLIBS_DIR}/ti/code/dsp/FPU/c28/include
)

add_library(${PROJECT_NAME} STATIC ${PROJ_DIR}/libstreaming.cpp)
set_target_properties(${PROJECT_NAME} PROPERTIES POSITION_INDEPENDENT_CODE TRUE)

target_link_libraries(${PROJECT_NAME}
${OpenCV_LIBS}
${WVLIBS_DIR}/project/cmake/build/libwvlibs.a
)


set_target_properties(${PROJECT_NAME} PROPERTIES
    CXX_STANDARD 11
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
)
