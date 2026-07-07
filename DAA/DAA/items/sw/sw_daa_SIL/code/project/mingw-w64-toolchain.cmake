set(CMAKE_SYSTEM_NAME Windows)
set(CMAKE_SYSTEM_PROCESSOR x86_64)

set(CMAKE_C_COMPILER clang)
set(CMAKE_CXX_COMPILER clang++)

set(CMAKE_C_FLAGS "--target=x86_64-w64-windows-gnu -g -gcodeview")
set(CMAKE_CXX_FLAGS "--target=x86_64-w64-windows-gnu -g -gcodeview")
set(CMAKE_EXE_LINKER_FLAGS "--target=x86_64-w64-windows-gnu -g -gcodeview")
set(CMAKE_SHARED_LINKER_FLAGS "--target=x86_64-w64-windows-gnu -g -gcodeview")

if(CMAKE_HOST_SYSTEM_NAME STREQUAL "Linux")
    # Cross-compiling from Linux (dev container) — need explicit sysroot
    set(CMAKE_RC_COMPILER x86_64-w64-mingw32-windres)
    set(CMAKE_FIND_ROOT_PATH /usr/x86_64-w64-mingw32)
    set(CMAKE_FIND_ROOT_PATH_MODE_PROGRAM NEVER)
    set(CMAKE_FIND_ROOT_PATH_MODE_LIBRARY ONLY)
    set(CMAKE_FIND_ROOT_PATH_MODE_INCLUDE ONLY)
endif()
# On Windows, Clang auto-discovers the mingw-w64 sysroot (e.g. Strawberry Perl)
