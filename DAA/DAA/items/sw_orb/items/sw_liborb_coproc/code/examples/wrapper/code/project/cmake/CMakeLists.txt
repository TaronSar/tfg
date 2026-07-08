# Archivo CMakeLists.txt

# Configuración mínima de CMake
cmake_minimum_required(VERSION 3.12)

# Nombre del proyecto
project(liborb_coproc_wrapper)

# Especificar el compilador de C++
set(CMAKE_CXX_COMPILER g++)

SET(PROJ_DIR ${PROJECT_SOURCE_DIR})

LIST(APPEND CMAKE_MODULE_PATH ${PROJECT_SOURCE_DIR}/cmake_modules)


find_package(OpenCV 4.4)



# Definir el ejecutable
add_executable(${PROJECT_NAME} ${PROJ_DIR}/../../source/main.cpp)

target_link_libraries(${PROJECT_NAME} ${PROJ_DIR}/../../source/liborb_coproc.a)

target_link_libraries(${PROJECT_NAME}
${OpenCV_LIBS}
)

# Establecer estándar de C++
set_target_properties(${PROJECT_NAME} PROPERTIES
    CXX_STANDARD 11
    CXX_STANDARD_REQUIRED YES
    CXX_EXTENSIONS NO
)