#!/bin/bash

# --- CONFIGURACIÓN DEL COMPILADOR (Descomentar la línea deseada) ---
# Para compilación cruzada (Xilinx ZYNQ 7000 2020.1 32-bits)
# CXX_COMPILER="arm-none-linux-gnueabihf-g++"
# Para compilación cruzada (Xilinx ZYNQ UltraScale+ 2020.1 64-bits)
# CXX_COMPILER="aarch64-linux-gnu-g++"
CXX_COMPILER="aarch64-xilinx-linux-g++"
# Si no se define ninguna, se usará el compilador por defecto del sistema (g++).


# Detener el script inmediatamente si algún comando falla.
set -e

# --- Detección de Rutas ---
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE}")" &> /dev/null && pwd)
BUILD_DIR="$SCRIPT_DIR/build"
PROJECT_ROOT_DIR=$(dirname "$SCRIPT_DIR")

# --- Lógica de Limpieza ---
# Si el primer argumento es "clean", borra el directorio de compilación y sale.
if [ "$1" == "clean" ]; then
    echo "Limpiando el directorio de compilación..."
    if [ -d "$BUILD_DIR" ]; then
        rm -rf "$BUILD_DIR"
        echo "Directorio '$BUILD_DIR' eliminado."
    else
        echo "El directorio de compilación no existe. No hay nada que limpiar."
    fi
    exit 0
fi


echo "Directorio del Proyecto: $PROJECT_ROOT_DIR"
echo "Directorio de Compilación: $BUILD_DIR"

# --- Creación del Directorio de Compilación ---
mkdir -p "$BUILD_DIR"

# --- Lógica del Compilador Personalizado ---
CMAKE_ARGS=""
# Comprueba si la variable CXX_COMPILER está definida y no está vacía.
if [ -n "$CXX_COMPILER" ]; then
    echo "Usando compilador personalizado: $CXX_COMPILER"
    # Pasa la ruta del compilador a CMake.
    CMAKE_ARGS="-D CMAKE_CXX_COMPILER=$CXX_COMPILER"
else
    echo "Usando el compilador C++ por defecto del sistema."
fi

# --- Ejecución de CMake y Make ---
echo "Configurando el proyecto con CMake..."
# Ejecuta CMake desde el directorio de compilación, apuntando a la raíz del proyecto.
cmake -S "$PROJECT_ROOT_DIR" -B "$BUILD_DIR" $CMAKE_ARGS

echo "Compilando el proyecto con make..."
# Ejecuta make desde el directorio de compilación.
# El argumento -j$(nproc) utiliza todos los núcleos de la CPU para acelerar la compilación.
make -C "$BUILD_DIR" -j$(nproc)

echo ""
echo "----------------------------------------------------"
echo "¡Compilación completada!"
echo "El ejecutable 'data_coordinator' se encuentra en:"
echo "$BUILD_DIR"
echo "Para limpiar los ficheros generados, ejecuta:"
echo "./builder.sh clean"
echo "----------------------------------------------------"
