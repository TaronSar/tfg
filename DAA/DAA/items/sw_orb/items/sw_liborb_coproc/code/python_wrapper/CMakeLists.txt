
cmake_minimum_required(VERSION 3.12)

project(orb_coproc_wrapper)

SET(PROJ_DIR ${PROJECT_SOURCE_DIR}/../python_wrapper/)
SET(VPROTO_DIR ${PROJECT_SOURCE_DIR}/../../../../../sw_vproto/code)
SET(COPROC_DUMMY_SRC ${VPROTO_DIR}/source/processes/liborb_coproc_dummy.cpp)
SET(LIB_COPROC_DIR ${PROJECT_SOURCE_DIR}/../)
# SET(VLIBS_DIR      ${PROJECT_SOURCE_DIR}/../../../../../Vlibs)

# Copy .pyi file
configure_file(
  ${PROJECT_SOURCE_DIR}/liborb_coproc_wrapper.pyi
  ${PROJECT_SOURCE_DIR}/../build/python_wrapper/liborb_coproc_wrapper.pyi
  COPYONLY
)

execute_process(
    COMMAND python3.12 -m pybind11 --cmakedir
    OUTPUT_VARIABLE PYBIND11_CMAKE_DIR
    OUTPUT_STRIP_TRAILING_WHITESPACE
)

list(APPEND CMAKE_PREFIX_PATH ${PYBIND11_CMAKE_DIR})
find_package(pybind11 2.13.0 REQUIRED)

#find_package(OpenCV 4.4)
MESSAGE(STATUS ${CROSS_ENV_PATH}/lib64/cmake/opencv4)
find_package(OpenCV 4.4 REQUIRED PATHS ${CROSS_ENV_PATH}/lib64/cmake/opencv4)
#find_package(OpenCV 4.4 REQUIRED PATHS ${OpenCV_PATH})

include_directories(${LIB_COPROC_DIR}/wrapper)

SET(SRC_FILES
    ${COPROC_DUMMY_SRC}
    liborb_coproc_wrapper.cpp)

MESSAGE(STATUS ${PROJECT_NAME})
add_library(${PROJECT_NAME} MODULE ${SRC_FILES})

# set_target_properties(${PROJECT_NAME} PROPERTIES POSITION_INDEPENDENT_CODE TRUE)

target_compile_options(${PROJECT_NAME} PRIVATE ${PYBIND11_INCLUDES})

target_link_libraries(${PROJECT_NAME} PRIVATE pybind11::module ${OpenCV_LIBS})

target_include_directories(${PROJECT_NAME} PRIVATE ${OpenCV_INCLUDE_DIRS})

set_target_properties(${PROJECT_NAME} PROPERTIES
    CXX_STANDARD 11
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
)