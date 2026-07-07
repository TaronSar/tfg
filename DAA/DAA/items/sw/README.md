# DAA Software

Detect-And-Avoid (DAA) software: conflict prediction, resolution,
trajectory generation and Monte-Carlo tooling.

## Layout

| Folder | Purpose |
| --- | --- |
| `sw_conflict_prediction/` | Intruder tracking / conflict prediction (estimators). |
| `sw_conflict_resolution/` | Avoidance core, candidate trajectories and the desktop app. |
| `sw_trajectory_generator/` | Encounter / trajectory generation (`cam_track_gen`). |
| `sw_montecarlo/` | Monte-Carlo batch tooling. |
| `sw_daa/`, `sw_daa_SIL/` | Core C++ DAA library and the Python↔C++ SIL shim. |

## Environment

Dependencies are defined in [`pyproject.toml`](pyproject.toml).

```sh
uv sync                 # create .venv from pyproject.toml + uv.lock
uv sync --extra build   # also install release tooling (PyInstaller)
```

Opening this folder in VS Code auto-detects the resulting `.venv`.

The local, in-repo wheel `cam_track_gen` is resolved automatically by
`uv`. With plain `pip`, install dependencies from `requirements.txt`,
add the wheel, then install this project itself in editable mode so the
`daa_*` packages are importable:

```sh
pip install -r requirements.txt
pip install --no-deps sw_trajectory_generator/package/cam_track_gen-0.1.0-py3-none-any.whl
pip install -e . --no-deps
```

`-e . --no-deps` registers the package mapping without re-resolving
dependencies (`cam_track_gen` declares an over-conservative
`networkx<3.0` bound; the pinned `networkx==3.6.1` is what actually
runs). `uv sync` handles the same case via an override and needs no
extra step.

## Running

The five `scripts/` folders are exposed as importable packages (see the
`[tool.setuptools]` mapping in [`pyproject.toml`](pyproject.toml)), so
modules are run with `python -m` rather than by file path:

```sh
python -m daa_montecarlo.run_montecarlo
python -m daa_trajectory_generator.generate_encounters
python -m daa_conflict_prediction.conflict_prediction
python -m daa_conflict_resolution.batch_avoidance
```

The desktop app:

```sh
python sw_conflict_resolution/app/daa_app.py
```

## Release

```sh
python sw_conflict_resolution/app/release.py
```

Builds the desktop app and produces `daa_app_v.<version>.zip`.
