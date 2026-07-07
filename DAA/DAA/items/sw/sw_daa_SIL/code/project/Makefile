.PHONY: build.linux build.windows cmake.gcc cmake.clang cmake.windows cmake.windows_release clear

build.linux:
	cd build && ninja DAA_SIL_linux/all

build.linux.j%:
	cd build && ninja DAA_SIL_linux/all -j$*

build.windows:
	cd build && ninja DAA_SIL/all

build.windows.j%:
	cd build && ninja DAA_SIL/all -j$*

cmake.gcc:
	cmake -B build -S . -G "Ninja" \
	-DCMAKE_C_COMPILER=gcc \
	-DCMAKE_CXX_COMPILER=g++ \
	-DCMAKE_BUILD_TYPE=Debug

cmake.gcc_release:
	cmake -B build -S . -G "Ninja" \
	-DCMAKE_C_COMPILER=gcc \
	-DCMAKE_CXX_COMPILER=g++ \
	-DCMAKE_BUILD_TYPE=Release

cmake.clang:
	cmake -B build -S . -G "Ninja" \
	-DCMAKE_C_COMPILER=clang \
	-DCMAKE_CXX_COMPILER=clang++ \
	-DCMAKE_BUILD_TYPE=Debug \
	-DCMAKE_CXX_FLAGS=-fmessage-length=0 \
	-DCMAKE_C_FLAGS=-fmessage-length=0

cmake.clang_release:
	cmake -B build -S . -G "Ninja" \
	-DCMAKE_C_COMPILER=clang \
	-DCMAKE_CXX_COMPILER=clang++ \
	-DCMAKE_BUILD_TYPE=Release \
	-DCMAKE_CXX_FLAGS=-fmessage-length=0 \
	-DCMAKE_C_FLAGS=-fmessage-length=0

cmake.windows:
	cmake -B build -S . -G "Ninja" \
	-DCMAKE_TOOLCHAIN_FILE=mingw-w64-toolchain.cmake \
	-DCMAKE_BUILD_TYPE=Debug

cmake.windows_release:
	cmake -B build -S . -G "Ninja" \
	-DCMAKE_TOOLCHAIN_FILE=mingw-w64-toolchain.cmake \
	-DCMAKE_BUILD_TYPE=Release

clear:
	cmake -E remove_directory build
	cmake -E make_directory build

redo:
	make clear
	make cmake.gcc
	make build.linux