# Cross-compilation environment for aarch64 (PetaLinux 2023.1)
# Base: Ubuntu 22.04 estandar, sin NVIDIA.
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=Europe/Madrid

# Paquetes base
RUN apt-get update && apt-get install -y \
    sudo \
    wget \
    curl \
    cmake \
    make \
    python3 \
    python3-pip \
    python3-dev \
    nano \
    git \
    unzip \
    yasm \
    pkg-config \
    build-essential \
    crossbuild-essential-arm64 \
    gdb-multiarch \
    sshpass \
    cppcheck \
    && rm -rf /var/lib/apt/lists/*

# Habilitar arquitectura arm64 y repos ports
RUN dpkg --add-architecture arm64 && \
    sed -i "s/deb h/deb [arch=amd64] h/g" /etc/apt/sources.list && \
    { \
      echo "# arm64 repositories"; \
      echo "deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy main restricted universe multiverse"; \
      echo "deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-updates main restricted universe multiverse"; \
      echo "deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-backports main restricted universe multiverse"; \
      echo "deb [arch=arm64] http://ports.ubuntu.com/ubuntu-ports jammy-security main restricted universe multiverse"; \
    } >> /etc/apt/sources.list

# Update tolerante a fallos parciales de los ports
RUN apt-get clean && apt-get update || true

# Dependencias arm64 (sysroot cruzado)
RUN apt-get install -y --fix-missing \
    libavcodec-dev:arm64 \
    libavformat-dev:arm64 \
    libavutil-dev:arm64 \
    libswscale-dev:arm64 \
    libswresample-dev:arm64 \
    libfreetype-dev:arm64 \
    libharfbuzz-dev:arm64 \
    libx264-dev:arm64 \
    libssl-dev:arm64 \
    libjpeg62:arm64 \
    libpng-dev:arm64 \
    libtiff-dev:arm64

# Dependencias host (gstreamer / ffmpeg / gtk / utils)
RUN apt-get install -y \
    ffmpeg \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer-plugins-bad1.0-dev \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    gstreamer1.0-tools \
    gstreamer1.0-x \
    gstreamer1.0-alsa \
    gstreamer1.0-gl \
    gstreamer1.0-gtk3 \
    gstreamer1.0-qt5 \
    gstreamer1.0-pulseaudio \
    libgtkglext1-dev \
    libavcodec-dev \
    libavformat-dev \
    libavutil-dev \
    libswscale-dev \
    libdc1394-dev \
    libgtk-3-dev \
    libgtk2.0-dev \
    libglib2.0-dev \
    libtbb2 \
    libtbb-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libpq-dev \
    libgdal-dev \
    python3-gdal \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libeigen3-dev

RUN mkdir -p /usr/aarch64-xilinx-linux

# Boost 1.83 cruzado a aarch64
RUN echo "Compiling boost 1.83 ..." && \
    wget https://archives.boost.io/release/1.83.0/source/boost_1_83_0.tar.gz && \
    tar -xzf boost_1_83_0.tar.gz && cd boost_1_83_0 && \
    sed -i '/if $(tag) = gcc && \[ numbers.less 4 $(version\[1\]) \]/,/\}/ s/^/    #/' tools/build/src/tools/common.jam && \
    ./bootstrap.sh --prefix=/usr/aarch64-xilinx-linux && \
    echo "using gcc : aarch64 : aarch64-linux-gnu-g++ : <arch>arm <address-model>64 ;" >> user-config.jam && \
    ./b2 toolset=gcc-aarch64 \
        --user-config=./user-config.jam \
        --prefix=/usr/aarch64-xilinx-linux \
        --layout=system \
        --build_type=complete \
        link=static runtime-link=static \
        install && \
    cd / && rm -rf /boost_1_83_0 /boost_1_83_0.tar.gz

# OpenCV 4.4 cruzado a aarch64, sin CUDA
RUN echo "Compiling opencv 4.4.0 ..." && \
    git clone --depth 1 --branch 4.4.0 https://github.com/Itseez/opencv.git /opencv && \
    git clone --depth 1 --branch 4.4.0 https://github.com/Itseez/opencv_contrib.git /opencv_contrib && \
    mkdir -p /opencv/build && cd /opencv/build && \
    cmake -D CMAKE_BUILD_TYPE=RELEASE \
    -D CMAKE_TOOLCHAIN_FILE=../platforms/linux/aarch64-gnu.toolchain.cmake \
    -D BUILD_SHARED_LIBS=OFF \
    -D BUILD_TIFF=ON \
    -D WITH_GSTREAMER=ON \
    -D WITH_CUDA=OFF \
    -D WITH_CUBLAS=OFF \
    -D WITH_CUFFT=OFF \
    -D WITH_NVCUVID=OFF \
    -D WITH_NVCUVENC=OFF \
    -D ENABLE_FAST_MATH=1 \
    -D ENABLE_AVX=OFF \
    -D WITH_OPENGL=ON \
    -D WITH_OPENCL=ON \
    -D WITH_IPP=OFF \
    -D WITH_TBB=ON \
    -D BUILD_TBB=ON \
    -D WITH_EIGEN=ON \
    -D WITH_V4L=ON \
    -D WITH_VTK=ON \
    -D BUILD_TESTS=OFF \
    -D BUILD_EXAMPLES=OFF \
    -D BUILD_PERF_TESTS=OFF \
    -D OPENCV_GENERATE_PKGCONFIG=ON \
    -D OPENCV_EXTRA_MODULES_PATH=/opencv_contrib/modules \
    -D CMAKE_INSTALL_PREFIX=/usr/aarch64-xilinx-linux/lib64/cmake/opencv4 \
    .. && \
    make -j"$(nproc)" && make install && \
    cd / && rm -rf /opencv /opencv_contrib

CMD ["/bin/bash"]
