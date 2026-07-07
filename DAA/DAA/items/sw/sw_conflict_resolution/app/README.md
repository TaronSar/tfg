# DAA Avoidance — desktop app

A standalone PySide6 desktop front-end for the avoidance simulator. Three
tabs:

1. **Parameters** — edit detection/maneuver/visualiser knobs (cylinder size,
   look-ahead time, lateral/vertical shift, transition time constant, …).
2. **Single seed** — run one encounter, see the classification summary,
   then pop the existing 3-D matplotlib animation.
3. **Monte Carlo** — run a batch over a contiguous seed range or a random
   sample, with parallel workers, a live progress bar, a results table and
   one-click CSV export.

## Run from source

```powershell
# from the workspace root, with the venv created (see ..\..\setup_venv.bat)
.\.venv\Scripts\Activate.ps1
.\.venv\Scripts\python sw_conflict_resolution\app\daa_app.py
```

## Build a standalone Windows executable

Requirements: PySide6 + PyInstaller in the venv (`pip install PySide6
pyinstaller`).

Before building, **make sure the estimator DLL is available**:

```
sw_daa_SIL\code\project\build\bin\libDAA_dll__sil.dll
```

(or copy it into `sw_conflict_prediction\scripts\estimators\`). The spec
file looks in both locations.

Then from the workspace root:

```powershell
.\.venv\Scripts\Activate.ps1
pyinstaller sw_conflict_resolution\app\daa_app.spec --clean --noconfirm
```

Output:

```
dist\daa_app\
    daa_app.exe
    libDAA_dll__sil.dll        (also under estimators\)
    ... Qt, numpy, matplotlib runtime ...
```

Zip the `dist\daa_app\` folder and ship it. Folder mode (~250 MB) is
required for two reasons:

* PyInstaller `--onefile` re-extracts to `%TEMP%` on every launch (slow),
  and it breaks the `ctypes.CDLL` lookup logic the estimator wrapper relies
  on.
* Multiprocessing on Windows spawns child processes via the same exe; the
  bootloader handles that correctly only with folder mode.

## Internals

* `daa_app.py::_bootstrap_paths()` runs *before* any project import and
  inserts `sw_conflict_resolution\scripts`, `sw_conflict_prediction\scripts`
  and the estimators folder into `sys.path`. When frozen by PyInstaller
  these directories are flattened next to `daa_app.exe`, and the function
  also calls `os.add_dll_directory(_MEIPASS)` so `ctypes.CDLL` can locate
  the bundled DLL.
* The Monte Carlo tab runs a `concurrent.futures.ProcessPoolExecutor`
  inside a `QThread` and re-emits each completed row as a Qt signal so the
  UI stays responsive.
* `if __name__ == '__main__': multiprocessing.freeze_support()` is called
  before any QApplication is constructed — required for the spawn-based
  child workers under a frozen exe.

## Troubleshooting

* **"OSError: could not load library libDAA_dll__sil.dll"** — the spec
  build couldn't find the DLL. Copy it into
  `sw_conflict_prediction\scripts\estimators\` and rebuild.
* **Monte Carlo workers crash with "module not found"** — make sure
  PyInstaller wasn't run with `--onefile`; use the supplied `daa_app.spec`.
* **Matplotlib window doesn't appear** — close any previous matplotlib
  figure; the visualiser opens a single blocking window per click.
