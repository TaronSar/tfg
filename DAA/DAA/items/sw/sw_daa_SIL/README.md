# DAA (Detect and Avoid) Software-in-the-Loop (SIL) Setup Guide

This guide provides instructions for setting up and building the SIL (Software-in-the-Loop) simulator for the DAA (Detect and Avoid) project.

## Prerequisites for Dev Container Compilation in Windows (Using Ubuntu)

If you want to compile inside a dev container (recommended for consistent development environment), follow these additional steps:

### 1. Install Ubuntu in Windows WSL

Install Windows Subsystem for Linux (WSL) with Ubuntu 24.04 LTS following the official Microsoft instructions:
- **Installation guide**: [https://learn.microsoft.com/es-es/windows/wsl/install#install-wsl-command](https://learn.microsoft.com/es-es/windows/wsl/install#install-wsl-command)

**Note**: The `Dockerfile` uses Ubuntu 20.04 to be compatible with a greater number of customers who might be using older distributions. This is the only reason to use an older distribution, so in the future it could be updated if necessary, for example when the long-term support (LTS) expires.

### 2. Install Docker Desktop
Download and install Docker Desktop for Windows:
- **Download link**: [https://www.docker.com/products/docker-desktop/](https://www.docker.com/products/docker-desktop/)

### 3. Install Dev Containers Extension

Install the "Dev Containers" extension in Visual Studio Code:
- Open VS Code
- Go to Extensions (Ctrl+Shift+X)
- Search for "Dev Containers" by Microsoft
- Install the extension

### 4. Open Project in Dev Container

Open the project using the Dev Container extension in VS Code:
- Open the project root folder in VS Code
- VS Code will automatically suggest opening the project in a dev container
- Accept the suggestion or use the Command Palette (Ctrl+Shift+P) and run "Dev Containers: Reopen in Container"

**Note**: The dev container includes all necessary tools (CMake, Clang, GCC, etc.) pre-installed, so you won't need to manually install the prerequisites listed above when using the dev container.

#### How to Reopen in Container

If you need to reopen the workspace in the container after closing it, use one of these methods:

1. **Command Palette Method** (Recommended):
   - Press `F1` or `Ctrl+Shift+P`
   - Type "Dev Containers: Reopen in Container"
   - Select it and press Enter

2. **Status Bar Method**:
   - Look for the remote connection indicator in the bottom-left corner of VS Code (looks like `><`)
   - Click it to open the remote connection menu
   - Select "Reopen in Container"

3. **Notification Prompt**:
   - VS Code may show a notification asking if you want to reopen in container
   - Click "Reopen in Container" if you see it

**Prerequisites**: Make sure Docker Desktop is running on your Windows machine before attempting to reopen in container.

## Prerequisites for Native Windows Compilation

### 1. CMake Installation

Download and install CMake from the official website:
- **Download link**: [https://cmake.org/download/](https://cmake.org/download/)

### 2. Clang Installation

Download and install Clang compiler:
- **Download link**: [LLVM-18.1.3-win64.exe](https://github.com/llvm/llvm-project/releases/download/llvmorg-18.1.3/LLVM-18.1.3-win64.exe)

### 3. Ninja Build System

Download Ninja build system and add it to your PATH environment variable:
- **Download link**: [ninja-win.zip](https://github.com/ninja-build/ninja/releases/download/v1.11.1/ninja-win.zip)
- **Note**: This is a portable executable, not an installer

### 4. MinGW-w64 Toolchain

A mingw-w64 installation is required to provide the C/C++ standard library headers and runtime libraries. Clang compiles the code but targets the mingw-w64 ABI via `--target=x86_64-w64-windows-gnu`.

You can install mingw-w64 from any of these sources:
- [MSYS2](https://www.msys2.org/) (recommended — install the `mingw-w64-x86_64-toolchain` package)
- [winlibs](https://winlibs.com/)
- [Mingw-w64 SourceForge builds](https://sourceforge.net/projects/mingw-w64/)

Clang will auto-discover the mingw-w64 sysroot when the target triple is set, as long as the `x86_64-w64-mingw32` headers and libraries are on the default search path.

### 5. GNU Make (Optional)

GNU Make is needed to use the `Makefile` build shortcuts (e.g. `make cmake.windows`, `make build.windows`). Install it via winget:

```powershell
winget install GnuWin32.Make
```

After installation, add `C:\Program Files (x86)\GnuWin32\bin` to your PATH.

Without `make`, you can run the CMake and Ninja commands directly in PowerShell (see build instructions below).

## Project Generation

### Step 0: Install Python Requirements (First Time Only)

Before running the VPGen script for the first time, you need to install the Python dependencies:

```bash
pip install -r ../sw_daa/items/_sw_perception/items/Vlibs/vpgen2/requirements.txt
```

**Note**: This step only needs to be performed once during the initial setup.

### Step 1: Run VPGen Script

Navigate to the directory `sw_daa_SIL/code/vpgen` and execute the existing `run.bat` script (on Windows):

```
cd sw_daa_SIL/code/vpgen
./run.bat  (Windows)
```

This script will generate the necessary CMake files for the project.

**Note**: You may see errors like "Unresolved dependency" or "Phantom target dependency" during script execution. These errors are normal and expected due to missing references to other projects that are not available in the current context.


### Step 2: Navigate to Project Root

Go to the DAA SIL project root directory `sw_daa_SIL/code/project` and run one of the following commands:

**For Linux builds:**
- **Linux with Clang:**
   ```bash
   make cmake.clang
   ```

**For Windows builds (cross-compilation from Linux, or native on Windows):**
- **Windows Debug build:**
   ```bash
   make cmake.windows
   ```

**Note 1**: The `mingw-w64-toolchain.cmake` toolchain file is OS-aware: on Linux it cross-compiles using the system mingw-w64 sysroot (`/usr/x86_64-w64-mingw32`), on Windows it lets Clang auto-discover the local mingw-w64 installation (e.g. Strawberry Perl). On Windows, if `make` is not available (e.g. in PowerShell), run the CMake command directly:
   ```powershell
   cmake -B build -S . -G "Ninja" -DCMAKE_TOOLCHAIN_FILE=mingw-w64-toolchain.cmake -DCMAKE_BUILD_TYPE=Debug
   cd build
   ninja DAA_SIL_windows__sil.exe
   ```

**Note 2**: You can see more `make` options in the Makefile in this same directory.

**Note 3**: For Windows (`cmake.windows`), `libstdc++` and `libgcc` are linked statically to prevent DLL hell and ensure the executables work across different Windows environments. For Linux (`cmake.clang` and `cmake.gcc`), these libraries are linked dynamically by default. Note however that the dynamic library (DLL or SO) interface has to be limited to plain C using `extern "C"`. No sharing of C++ objects in the interface is allowed.

**Note 4**: Statically linking `libstdc++` and `libgcc` in Linux prevents the dynamic library from being properly unloaded from memory, as the statically linked libraries maintain references that keep the module resident. This is why dynamic linking is preferred for shared libraries on Linux.

## Building Components

After running the CMake configuration, navigate to the `sw_daa_SIL/code/project/build` directory created by CMake:

```bash
cd sw_daa_SIL/code/project/build
```

### Linux Targets

| Target | Description |
|--------|-------------|
| `DAA_SIL_linux__sil` | Standalone SIL executable for Linux |
| `DAA_so__sil` | DAA shared library (`.so`) for Linux |

```bash
ninja DAA_SIL_linux__sil
ninja DAA_so__sil
```

### Windows Targets

| Target | Description |
|--------|-------------|
| `DAA_SIL_windows__sil` | Standalone SIL executable for Windows |
| `DAA_dll__sil` | DAA dynamic library (`.dll`) for Windows |

```bash
ninja DAA_SIL_windows__sil
ninja DAA_dll__sil
```



## Running DAA SIL (Inside the Container)

Navigate to `sw_daa_SIL/code/project/build/bin` and run the DAA_SIL_linux executable with appropriate parameters as needed.

**Note 1**: The container setup and port forwarding are configured in `.devcontainer/devcontainer.json`.

**Note 2**: In the file `.devcontainer/devcontainer.json`, port 56777 is exposed to the outside for external communication.



## Directory Structure

```
sw_daa_SIL/
├── code/
│   ├── vpgen/
│   │   ├── projects.json  # VPGen configuration
│   │   ├── projects0.json # VPGen project specifics
│   │   └── run.bat        # VPGen script
│   ├── project/
│   │   ├── CMakeLists.txt # CMake configuration
│   │   ├── Makefile       # Build makefile
│   │   ├── build/         # Generated by CMake
│   │   └── DAA_SIL_linux/ # Main executable source
│   └── (other source files)
├── .devcontainer/
│   ├── devcontainer.json  # Dev container configuration
│   └── Dockerfile         # Docker image definition
└── README.md              # This file
```