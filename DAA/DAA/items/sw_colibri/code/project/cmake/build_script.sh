#!/bin/bash

mkdir build
cd build
cmake -D OpenCV_INCLUDE_DIRS=/usr/include/opencv4/ -D OpenCV_LIBS=/usr/lib/aarch64-linux-gnu -D CMAKE_BUILD_TYPE=Release ..

make -j8
