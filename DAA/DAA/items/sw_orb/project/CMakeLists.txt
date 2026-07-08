cmake_minimum_required(VERSION 3.0.2)
project(sw_daa)

SET(ORB_SLAM3_DIR ${PROJECT_SOURCE_DIR}/../../../items/ORB_SLAM3)
SET(VLIBS_DIR      ${PROJECT_SOURCE_DIR}/../../../../../items/Vlibs)
SET(DAA_DIR ${PROJECT_SOURCE_DIR}/../../../code)
SET(DAA_SRC ${PROJECT_SOURCE_DIR}/../../../code/source)
SET(DAA_INC ${PROJECT_SOURCE_DIR}/../../../code/include)
SET(ITEMS_DIR ${PROJECT_SOURCE_DIR}/../../../items/)
#SET(SOPHUS_DIR ${PROJECT_SOURCE_DIR}/../../../items/Sophus)
#SET(DBOW2_DIR ${PROJECT_SOURCE_DIR}/../../../items/DBoW2)
SET(G2O_DIR ${PROJECT_SOURCE_DIR}/../../../items/g2o)

include_directories(
    ${VLIBS_DIR}/geomodel/code/include
    ${VLIBS_DIR}/base/code/include
    ${VLIBS_DIR}/first/code/include
    ${VLIBS_DIR}/ti/code/dsp/FPU/c28/include
    ${VLIBS_DIR}/maverick/code/include_SIL
    ${VLIBS_DIR}/maverick/code/include
    ${VLIBS_DIR}/bsp/code/include_SIL
    ${VLIBS_DIR}/bsp/code/include
    ${DAA_INC}
)

add_library(${PROJECT_NAME} STATIC
    ${DAA_SRC}/System.cpp
)

target_link_libraries(${PROJECT_NAME}
    ${VLIBS_DIR}/geomodel/code/project/cmake/build/libgeomodel.a
    ${VLIBS_DIR}/maverick/code/project/cmake/build/libmaverick.a
    ${VLIBS_DIR}/first/code/project/cmake/build/libfirst.a
    ${VLIBS_DIR}/base/code/project/cmake/build/libbase.a
    ${VLIBS_DIR}/bsp/code/project/cmake/build/libbsp.a
    ${VLIBS_DIR}/geomodel/code/project/cmake/build/libgeomodel.a
    ${VLIBS_DIR}/maverick/code/project/cmake/build/libmaverick.a
    ${VLIBS_DIR}/first/code/project/cmake/build/libfirst.a
    ${VLIBS_DIR}/base/code/project/cmake/build/libbase.a
    ${VLIBS_DIR}/bsp/code/project/cmake/build/libbsp.a
)

add_executable(example
    ${DAA_SRC}/example.cpp
)

target_link_libraries(example
    ${PROJECT_NAME}
)

#link_directories(${VLIBS_DIR}/build/lib/)