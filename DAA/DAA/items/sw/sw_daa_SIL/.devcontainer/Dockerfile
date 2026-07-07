FROM mcr.microsoft.com/devcontainers/cpp:ubuntu-20.04

RUN apt-get update && \
    apt-get install -y \
    cmake \
    gdb \
    clang-tidy \
    clang-format \
    mingw-w64 \
    mingw-w64-common \
    mingw-w64-tools \
    gcc-mingw-w64-x86-64 \
    g++-mingw-w64-x86-64 \
    python3-pip && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*
