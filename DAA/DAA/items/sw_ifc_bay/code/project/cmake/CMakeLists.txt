cmake_minimum_required(VERSION 3.0.2)
project(ifc_bay)


set(CMAKE_VERBOSE_MAKEFILE ON)

###########
## Build ##
###########
#set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -Wl,--no-as-needed")
set(CMAKE_C_FLAGS "${CMAKE_C_FLAGS} -O3 -DVERBOSE")
set(CMAKE_CXX_FLAGS "${CMAKE_CXX_FLAGS} -O3 -std=c++17 -DVERBOSE -pthread")


SET(VLIBS_DIR  ${PROJECT_SOURCE_DIR}/../../../../Vlibs)

set(THREADS_PREFER_PTHREAD_FLAG ON)

file(GLOB SOURCE_FILES
    "${PROJECT_SOURCE_DIR}/../../source/*.cpp"
)

include_directories(
    ${PROJECT_SOURCE_DIR}/../../include
    ${VLIBS_DIR}/bsp/code/include
)

add_executable(${PROJECT_NAME} ${SOURCE_FILES} ${PROJECT_SOURCE_DIR}/../../test/${MAIN_FILE}.cpp)


target_link_libraries(${PROJECT_NAME}
)