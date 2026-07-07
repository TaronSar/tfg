# Copilot Cloud Agent Instructions — LM Repository

> **Trust these instructions first.** Only perform additional exploration if information here is incomplete or found to be in error.

## 1. Repository Summary

**LM** (Loitering Munition) is an embedded C++17 perception system by **Embention** for autonomous UAV navigation. It integrates ORB SLAM based GNSS-denied navigation, visual odometry, object detection (YOLO on CUDA/TI DPU), point tracking, RTSP/TCP streaming, CAN bus communication, and MAVLink. The final artifact is a cross-compiled `lm` executable targeting **aarch64** (NVIDIA Jetson, Xilinx Ultrascale+, TI Jacinto).

- **Languages**: C++17 (primary), bash scripts, CMake
- **Build system**: CMake 3.22, GNU Make
- **Compilers**: `aarch64-linux-gnu-g++` 11.4.0 (cross, default via `$COMPILER_PREFIX`), native `g++` 11.4.0
- **Key dependencies**: OpenCV 4.4.0 (static, cross at `/usr/aarch64-xilinx-linux/lib64/cmake/opencv4`), Eigen3 3.4, Boost 1.83 (cross at `/usr/aarch64-xilinx-linux/lib/`), libx264, ONNX Runtime 1.16/1.18
- **Container OS**: Ubuntu 22.04 (CUDA 12.6 devcontainer with cross-compilation toolchains)

## 2. Repository Layout

```
/workspace/
├── code/main1/code/                     # Main LM executable
│   ├── source/main.cpp                  # Entry point (1083 lines)
│   └── project/cmake/CMakeLists.txt     # Builds `lm` binary
├── items/_sw_perception/                # Core perception library (git submodule: embention/sw_perception)
│   ├── code/
│   │   ├── source/                      # ~90 .cpp files (feature extraction, matching, tracking, VO, comms)
│   │   ├── include/                     # ~150 headers
│   │   └── project/cmake/CMakeLists.txt # Builds libsw_perception.a (399 lines)
│   ├── items/
│   │   ├── Vlibs/                       # Embention avionics libraries (submodule: embention/Vlibs)
│   │   │   ├── bsp/ base/ first/ geomodel/ maverick/ pring/ devices/ media/ DFS2/ stanag/
│   │   │   └── lib/                     # Aggregated .a files copied by cross_build_vlibs.sh
│   │   ├── sw_gnssdenied/               # GNSS-denied subsystem
│   │   │   ├── items/sw_orbslam/        # ORB-SLAM3 → lib/libORB_SLAM3.a
│   │   │   ├── items/sw_dbow/           # DBoW2 → lib/libDBoW2.a
│   │   │   ├── items/sw_g2o/            # g2o → lib/libg2o.a
│   │   │   ├── items/sw_wvlibs/         # Wrapped Vlibs → build/libwvlibs.a
│   │   │   └── items/sw_sophus/         # Sophus Lie group (header-only)
│   │   ├── sw_orb/items/sw_liborb_coproc/ # Coprocessor lib → build/liborb_coproc.a
│   │   ├── sw_rtsp/                     # RTSP server → build/librtsp.a
│   │   └── sw_mavlink/                  # MAVLink headers
│   └── .clang-format                    # Code formatting config
├── ci/Jenkinsfile_repository            # Jenkins CI (uses shared ci_library)
├── .github/
│   ├── pull_request_template.md         # PR template with changelog + checklist
│   └── workflows/                       # Issue/release automation (no PR build checks)
└── .gitmodules                          # 3 submodules: _accesories, _Avionics, _sw_perception
```

**Key environment variables** (pre-set in devcontainer):
- `CROSS_ENVIROMENT=/usr/aarch64-xilinx-linux` — cross-compilation sysroot
- `COMPILER_PREFIX=aarch64-linux-gnu-` — cross-compiler prefix

## 3. Build Instructions

### 3a. Build Order (bottom-up dependency chain)

Always build dependencies **before** dependents. The full build chain is:

1. **Vlibs** (independent libraries, build in this exact order)
2. **sw_dbow, sw_sophus, sw_g2o, sw_orbslam** (SLAM dependencies)
3. **sw_wvlibs** (wrapped Vlibs)
4. **sw_rtsp** (RTSP server)
5. **sw_liborb_coproc** (coprocessor lib)
6. **libsw_perception.a** (perception library, depends on all above)
7. **lm** (final executable, depends on libsw_perception.a + all libs)

### 3b. Building a Single Vlib Component (example: geomodel)

```bash
cd /workspace/items/_sw_perception/items/Vlibs/geomodel/code/project/cmake/build
rm -rf *
cmake -DCMAKE_BUILD_TYPE=Release ..
make -j4
```

Each Vlib is a static library under `items/_sw_perception/items/Vlibs/<name>/code/project/cmake/`. The `build/` directory already exists for all modules. Available modules: `bsp`, `base`, `first`, `geomodel`, `maverick`, `pring`, `devices`, `media`, `DFS2`, `stanag`.

### 3c. Building All Vlibs (cross-compile)

```bash
cd /workspace/items/_sw_perception/items/sw_gnssdenied/code/project/scripts
./cross_build_vlibs.sh
```

### 3d. Building libsw_perception.a

```bash
cd /workspace/items/_sw_perception/code/project/cmake/build
rm -rf *
export DAA_TEXAS=0 COPROC=0 BUILD_TYPE=Release VBN_THREAD=1 VIEWER_DEBUG=0 VBN_SIL=0 DAA_ROS=0 CUDA_12=0
cmake -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
  -DCMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
  -DCMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
  -DCROSS_ENV_PATH=${CROSS_ENVIROMENT} \
  -DCMAKE_COPROC=${COPROC} \
  -DCMAKE_VBN_THREADS=${VBN_THREAD} \
  -DCMAKE_VIEWER_DEBUG=${VIEWER_DEBUG} \
  -DCMAKE_VBN_SIL=${VBN_SIL} \
  -DCMAKE_DAA_TEXAS=${DAA_TEXAS} \
  -DCMAKE_DAA_ROS=${DAA_ROS} \
  -DCMAKE_CUDA_12=${CUDA_12} ..
make -j4
```

### 3e. Building the LM Executable

**IMPORTANT**: Always add `-L/usr/lib/aarch64-linux-gnu` to the linker flags:

```bash
cd /workspace/code/main1/code/project/cmake/build
rm -rf *
export DAA_TEXAS=0 COPROC=0 BUILD_TYPE=Release CUDA_12=0
cmake -DCMAKE_BUILD_TYPE=${BUILD_TYPE} \
  -DCMAKE_DAA_TEXAS=${DAA_TEXAS} \
  -DSRC_MAIN=main1/code/source/main.cpp \
  -DCROSS_ENV_PATH=${CROSS_ENVIROMENT} \
  -DCMAKE_C_COMPILER=${COMPILER_PREFIX}gcc \
  -DCMAKE_CXX_COMPILER=${COMPILER_PREFIX}g++ \
  -DCMAKE_CUDA_12=${CUDA_12} \
  -DCMAKE_EXE_LINKER_FLAGS="-L/usr/lib/aarch64-linux-gnu" ..
make -j4
```

**Known issue**: Without `-DCMAKE_EXE_LINKER_FLAGS="-L/usr/lib/aarch64-linux-gnu"`, linking fails with `cannot find -lx264`. The arm64 libx264 is installed at `/usr/lib/aarch64-linux-gnu/libx264.a` but the cross-linker does not search there by default.

### 3f. Full End-to-End Build (using build task chain)

The VS Code tasks define the full sequence: `build sw_wvlibs` → `build sw_perception SW` → `build sw_lm` → `send lm Nano`. The build scripts are in:
- `/workspace/items/_sw_perception/items/sw_gnssdenied/code/project/scripts/cross_build_wvlibs.sh`
- `/workspace/items/_sw_perception/code/project/scripts/cross_build_perception.sh`
- `/workspace/code/main1/code/project/scripts/cross_build_lm.sh`

## 4. Code Style & Conventions

- **C++ standard**: C++17 (`-std=c++17` in CMake)
- **Formatting**: `.clang-format` at `items/_sw_perception/.clang-format` — Google-based, 119 col limit, 4-space indent, Allman braces, `SortIncludes: Never`. No clang-tidy or other static analysis tools are configured or used.
- **Namespace**: `Vbn` for perception code
- **Naming**: PascalCase for classes (`Pcapturing`, `Llhpframe`); prefix `P` = process class, `I` = interface, `T` = template type
- **Comments**: All new code comments must be written in **English**. Existing codebase has a mix of English and Spanish, but new contributions use English only. `//` inline style. Phase-numbered comments for multi-step operations.
- **Compiler flags**: `-Wall -O3` for Release builds; warnings exist for `-Wreorder`, `-Wsign-compare`, `-Wunused-variable` (these are expected and not treated as errors)

### 4.1 JSF++ Coding Standards (JSF AV C++ Rules)

All new C++ code **must** comply with the **Joint Strike Fighter Air Vehicle C++ Coding Standards** (Doc 2RDU00001 Rev C). For exhaustive code reviews, consult the complete rule listing in `.github/JSF-AV-CPP-rules.md`. Key rules that directly affect code generation:

**Function design:**
- AV Rule 1: Max **200 logical source lines** per function/method.
- AV Rule 3: Cyclomatic complexity **≤ 20** per function.
- AV Rule 110: Max **7 arguments** per function.
- AV Rule 111: Never return a pointer or reference to a non-static local object.

**Style & formatting:**
- AV Rule 41: Lines **≤ 120 characters**.
- AV Rule 42: One expression-statement per line.
- AV Rule 43: No tabs — use spaces.
- AV Rule 44: Indent at least 2 spaces (project uses 4), consistent within file.
- AV Rule 45: Words in identifiers separated by `_`.
- AV Rule 47: Identifiers must not begin with `_`.
- AV Rule 50: Class/struct/enum/namespace names: first word starts uppercase, rest lowercase.
- AV Rule 51: Function and variable names: all lowercase.
- AV Rule 60–61: Allman braces — opening and closing braces on their own lines, same column.
- AV Rule 62: `*` and `&` attached to the type, not the variable name (`int* p`, not `int *p`).
- AV Rule 152: One variable declaration per line.

**Preprocessor:**
- AV Rule 27–28: Use `#ifndef`/`#define`/`#endif` include guards only.
- AV Rule 29: No `#define` macros — use `inline` functions.
- AV Rule 30–31: No `#define` constants — use `const`.

**Classes:**
- AV Rule 57: Declare sections in order: `public`, `protected`, `private`.
- AV Rule 67: Public/protected data only in `struct`, never in `class`.
- AV Rule 69: Non-mutating member functions must be `const`.
- AV Rule 74–75: Use member initialization lists, in declaration order.
- AV Rule 76: Define copy constructor + assignment operator for classes with pointers.
- AV Rule 78: Base classes with virtual functions must have a virtual destructor.
- AV Rule 79: All resources acquired by a class must be released in the destructor.
- AV Rule 82: `operator=` must return `*this` by reference.
- AV Rule 88: Multiple inheritance restricted to interfaces + private implementations.

**Safety-critical restrictions:**
- AV Rule 175: Use `0` (or `nullptr` in C++17), not `NULL`.
- AV Rule 185: Use C++ casts (`static_cast`, `reinterpret_cast`, `const_cast`), never C-style casts.
- AV Rule 208: **No C++ exceptions** (`throw`, `catch`, `try` shall not be used).
- AV Rule 162–163: Do not mix signed and unsigned; avoid unsigned arithmetic.

**Flow control:**
- AV Rule 59: Always use braces `{}` for `if`/`else`/`while`/`do`/`for` bodies.
- AV Rule 198–200: `for` loop init/increment must only affect the loop variable; use `while` if no init or increment is needed.

## 5. CI/CD & Validation

- **Jenkins**: `ci/Jenkinsfile_repository` uses shared `ci_library` with `pipelines_common()`. The same pattern exists in `items/_sw_perception/ci/` and `items/_sw_perception/items/Vlibs/ci/`.
- **GitHub Workflows**: Focused on issue management, release tagging, and approval checks — **no automated build/test on PR**. Key workflow: `check_approvals.yml` (Vlibs) requires **3 code approvals + 1 non-code approval**.
- **PR template**: Changelog sections (Added/Removed/Changed/Fixed) + extensive checklist of verification procedures.
- **No automated test suite** is run in CI. Test programs exist under `items/_sw_perception/code/test/` (32 example programs) but are individually built and run manually.

## 6. Validation After Changes

After modifying code, always verify by rebuilding the affected component and its dependents:

1. If changing files in `items/_sw_perception/code/source/` → rebuild `libsw_perception.a` (step 3d)
2. If changing files in `code/main1/code/source/main.cpp` → rebuild `lm` (step 3e)
3. If changing Vlibs → rebuild that Vlib module, then `libsw_perception.a`, then `lm`
4. Check build output for new warnings — existing warnings (`-Wreorder`, `-Wsign-compare`, `-Wunused-variable`) are acceptable but new errors must be resolved

## 7. Important Notes

- **Git submodules**: `items/_sw_perception` is `embention/sw_perception.git` (branch: `develop`); `items/Vlibs` is `embention/Vlibs.git` (branch: `feature/DAA/74_vbn`). Changes to submodule code belong in the respective submodule repo.
- **Cross-compilation is the default**. The `$COMPILER_PREFIX` env var is set to `aarch64-linux-gnu-` so all CMake commands that use `${COMPILER_PREFIX}gcc` will cross-compile. Native (x86_64) builds require unsetting or overriding `COMPILER_PREFIX`.
- **Pre-built libraries** exist in `build/` directories throughout the tree. Incremental builds (`make -j4` without `rm -rf *`) are safe and fast. Only clean (`rm -rf *`) when CMake configuration changes.
- **No linter or static analysis** tool is configured. Only `.clang-format` exists for auto-formatting. JSF++ compliance is enforced by code review (see Section 4.1).
- **Target platforms**: NVIDIA Jetson (Orin/Nano), Xilinx Ultrascale+ (ZUS+), TI Jacinto (J784S4). Platform selection is via `DAA_TEXAS=1` (TI) vs default (NVIDIA/Xilinx).
