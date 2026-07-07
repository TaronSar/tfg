# PyInstaller spec for the DAA Avoidance desktop application.
#
# Build (from the workspace root, with the venv activated):
#     pyinstaller sw_conflict_resolution\app\daa_app.spec --clean --noconfirm
#
# The output is a *folder* bundle in ``dist\daa_app\`` containing
# ``daa_app.exe`` plus all required DLLs / data files.  Folder mode is
# preferred over one-file mode because:
#   * onefile unpacks to %TEMP% on every launch (slow, ~10 s)
#   * onefile re-extracts the bundled DLLs each time, which breaks the
#     ctypes search heuristics in daa_estimators_wrapper.py
#
# The application relies on the project packages being installed (editable
# is fine: ``pip install -e .`` / ``uv sync`` from the ``sw`` root).  Their
# DLL is located at runtime by ``daa_dll.load()``, which searches the
# PyInstaller ``_MEIPASS`` extraction root when frozen.

import os
import sys
from pathlib import Path

# --- Paths -------------------------------------------------------------------
HERE      = Path(os.path.abspath(SPECPATH))           # sw_conflict_resolution/app
SW_ROOT   = HERE.parent.parent                         # .../sw
CP_SCRIPT = SW_ROOT / 'sw_conflict_prediction' / 'scripts'
ESTIM     = CP_SCRIPT / 'estimators'
DLL_BUILD_WIN = SW_ROOT / 'sw_daa_SIL' / 'code' / 'project' / 'build' / 'bin'
DLL_BUILD_LIN = SW_ROOT / 'sw_daa_SIL' / 'code' / 'project' / 'build' / 'DAA_so'

# --- Locate the estimator shared library (DLL on Windows, .so on Linux) -----
def _find_dll() -> str:
    candidates = [
        # Linux
        ESTIM          / 'libDAA_so__sil.so',
        ESTIM          / 'daa_estimators.so',
        DLL_BUILD_LIN  / 'libDAA_so__sil.so',
        DLL_BUILD_LIN  / 'daa_estimators.so',
        # Windows
        ESTIM          / 'libDAA_dll__sil.dll',
        ESTIM          / 'daa_estimators.dll',
        DLL_BUILD_WIN  / 'libDAA_dll__sil.dll',
        DLL_BUILD_WIN  / 'daa_estimators.dll',
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    raise FileNotFoundError(
        'Could not locate the estimator shared library. '
        'Build sw_daa_SIL or copy libDAA_so__sil.so (Linux) / '
        'libDAA_dll__sil.dll (Windows) into '
        'sw_conflict_prediction/scripts/estimators/.')

DLL_PATH = _find_dll()
print(f'[spec] bundling estimator DLL: {DLL_PATH}')

# Drop the DLL at the bundle root.  ``daa_dll.load()`` adds ``_MEIPASS`` and
# the executable directory to its search list when running frozen.
binaries = [(DLL_PATH, '.')]
datas = []

# --- Project packages --------------------------------------------------------
# With uv editable installs and a custom ``package-dir`` mapping the
# setuptools stubs placed in site-packages are NOT reliably followed by
# PyInstaller's import tracer.  We therefore copy the real source trees
# explicitly into the bundle under the correct package names.
_PROJECT_SRCS = [
    ('daa_conflict_resolution', SW_ROOT / 'sw_conflict_resolution' / 'scripts'),
    ('daa_conflict_prediction', SW_ROOT / 'sw_conflict_prediction' / 'scripts'),
    ('daa_trajectory_generator', SW_ROOT / 'sw_trajectory_generator' / 'scripts'),
    ('daa_montecarlo',           SW_ROOT / 'sw_montecarlo'           / 'scripts'),
    ('daa_sil',                  SW_ROOT / 'sw_daa_SIL'              / 'scripts'),
]
for _pkg, _src in _PROJECT_SRCS:
    if _src.exists():
        datas.append((str(_src), _pkg))
    else:
        print(f'[spec] WARNING: source directory not found for {_pkg}: {_src}')

# --- Analysis ----------------------------------------------------------------
# collect_submodules still feeds hiddenimports so PyInstaller compiles the
# modules into the PYZ archive (faster startup).  The datas entries above
# act as a reliable fallback if the editable-install tracer misses files.
from PyInstaller.utils.hooks import collect_all, collect_submodules

# The project packages are installed *editable* with a remapped layout
# (``[tool.setuptools.package-dir]`` maps e.g. ``daa_conflict_resolution`` ->
# ``sw_conflict_resolution/scripts``).  Modern setuptools implements that via a
# PEP 660 ``MetaPathFinder`` placed on ``sys.meta_path``.  PyInstaller's module
# graph resolves imports by scanning ``pathex`` / ``sys.path`` directories and
# does NOT execute meta-path finders, so ``collect_submodules`` finds nothing
# and the packages are silently omitted -> ``ModuleNotFoundError`` at runtime.
#
# Resolve the mapping ourselves: walk each remapped source directory and inject
# every ``.py`` into the analysis under its proper dotted package name (done
# below, after ``Analysis``, via ``a.pure``).  This is independent of the
# editable-install finder, so the bundle works regardless of how (or whether)
# the project is installed in the build venv.
PROJECT_PACKAGE_DIRS = {
    'daa_conflict_prediction':  SW_ROOT / 'sw_conflict_prediction' / 'scripts',
    'daa_conflict_resolution':  SW_ROOT / 'sw_conflict_resolution' / 'scripts',
    'daa_trajectory_generator': SW_ROOT / 'sw_trajectory_generator' / 'scripts',
    'daa_montecarlo':           SW_ROOT / 'sw_montecarlo' / 'scripts',
    'daa_sil':                  SW_ROOT / 'sw_daa_SIL' / 'scripts',
}

project_pymodules = []   # (dotted_name, abs_source_path)
for _pkg, _root in PROJECT_PACKAGE_DIRS.items():
    if not _root.is_dir():
        raise FileNotFoundError(f'project source dir missing: {_root}')
    for _py in sorted(_root.rglob('*.py')):
        if '__pycache__' in _py.parts:
            continue
        _parts = list(_py.relative_to(_root).with_suffix('').parts)
        if _parts and _parts[-1] == '__init__':
            _parts = _parts[:-1]
        _dotted = '.'.join([_pkg, *_parts])
        project_pymodules.append((_dotted, str(_py)))

print(f'[spec] injecting {len(project_pymodules)} project modules')

ctg_datas, ctg_bins, ctg_hidden = collect_all('cam_track_gen')

_mp_spawn = (
    ['multiprocessing.popen_spawn_win32']
    if sys.platform == 'win32'
    else ['multiprocessing.popen_fork', 'multiprocessing.popen_forkserver']
)

# The project modules are injected straight into ``a.pure`` (below) without
# import-graph analysis, so any third-party module reached *only* through a
# project submodule is invisible to PyInstaller and must be named here.  The
# 3-D visualiser (``visualize_avoidance`` / ``visualize_trajectories``) is the
# main culprit: it pulls in ``mpl_toolkits.mplot3d`` plus several matplotlib
# submodules that ``daa_app.py`` itself never imports.  ``mpl_toolkits`` is a
# separate namespace package that matplotlib's own hook does not cover, so
# collect all of its submodules explicitly.
viz_hidden = collect_submodules('mpl_toolkits')

hiddenimports = [
    'multiprocessing',
    'multiprocessing.pool',
    'concurrent.futures.process',
] + _mp_spawn + [
    'matplotlib.backends.backend_qtagg',
    'matplotlib.backends.backend_tkagg',
    # matplotlib submodules used only by the project visualisers.
    'matplotlib.animation',
    'matplotlib.widgets',
    'matplotlib.patches',
    'matplotlib.gridspec',
    'mpl_toolkits.mplot3d',
    'mpl_toolkits.mplot3d.art3d',
    'mpl_toolkits.mplot3d.proj3d',
    'scipy.special._cdflib',
    'h5py.defs', 'h5py.utils', 'h5py._proxy',
    'numpy',
    'pandas',
    'cam_track_gen',
] + viz_hidden + ctg_hidden

datas    = datas    + ctg_datas
binaries = binaries + ctg_bins

a = Analysis(
    [str(HERE / 'daa_app.py')],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=['tkinter', 'PyQt5', 'PyQt6'],
    noarchive=False,
)

# Inject the remapped project modules into the pure-Python module table so they
# are compiled into the PYZ under their proper dotted names.  Skip any name the
# graph already resolved (e.g. if a future build venv exposes them as plain
# packages) to avoid duplicate entries.
_already = {name for name, *_ in a.pure}
a.pure += [(name, path, 'PYMODULE')
           for name, path in project_pymodules
           if name not in _already]

pyz = PYZ(a.pure, a.zipped_data)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='daa_app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,                 # Set True to keep a console for debugging
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe, a.binaries, a.zipfiles, a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name='daa_app',
)
