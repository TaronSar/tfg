#!/usr/bin/env python3
"""Build and package the DAA Avoidance desktop application release.

Runs PyInstaller on ``daa_app.spec`` and zips the resulting
``dist/daa_app`` folder bundle into ``daa_app_v.<version>.zip`` (version
read from :mod:`_version`).

The script is path-independent: it resolves every input relative to its
own location, so it can be launched from any working directory, e.g.::

    python C:\\...\\sw_conflict_resolution\\app\\release.py
    python release.py --output-dir D:\\releases

By default the zip is written to the current working directory.  Build
artefacts go under ``<sw>/build`` (work) and ``<sw>/dist`` (bundle).
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

# --- Paths (resolved relative to this file, not the CWD) --------------------
APP_DIR = Path(__file__).resolve().parent                 # .../sw_conflict_resolution/app
SW_ROOT = APP_DIR.parent.parent                            # .../sw
SPEC    = APP_DIR / 'daa_app.spec'
VERSION_FILE = APP_DIR / '_version.py'

DIST_PATH = SW_ROOT / 'dist'                               # PyInstaller --distpath
WORK_PATH = SW_ROOT / 'build'                              # PyInstaller --workpath
BUNDLE    = DIST_PATH / 'daa_app'                          # folder bundle output


def read_version() -> str:
    """Read ``__version__`` from ``_version.py`` without importing the package."""
    namespace: dict = {}
    code = VERSION_FILE.read_text(encoding='utf-8')
    exec(compile(code, str(VERSION_FILE), 'exec'), namespace)
    version = namespace.get('__version__')
    if not version:
        raise RuntimeError(f'__version__ not found in {VERSION_FILE}')
    return str(version)


def run_pyinstaller(extra_args: list[str]) -> None:
    """Invoke PyInstaller on the spec using the current interpreter's venv."""
    try:
        import PyInstaller.__main__ as pyi_main
    except ImportError as exc:  # pragma: no cover - environment guard
        raise SystemExit(
            'PyInstaller is not installed in this interpreter. Activate the '
            'project venv and `pip install pyinstaller`, then re-run.'
        ) from exc

    args = [
        str(SPEC),
        '--clean',
        '--noconfirm',
        '--distpath', str(DIST_PATH),
        '--workpath', str(WORK_PATH),
        *extra_args,
    ]
    print(f'[release] pyinstaller {" ".join(args)}')
    pyi_main.run(args)


def zip_bundle(zip_path: Path) -> None:
    """Zip the ``dist/daa_app`` folder so it extracts to ``daa_app/``."""
    if not BUNDLE.is_dir():
        raise SystemExit(
            f'Expected bundle folder not found: {BUNDLE}\n'
            'The PyInstaller build did not produce dist/daa_app.')
    if zip_path.exists():
        zip_path.unlink()
    print(f'[release] zipping {BUNDLE} -> {zip_path}')
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(BUNDLE.rglob('*')):
            if path.is_file():
                arcname = Path('daa_app') / path.relative_to(BUNDLE)
                zf.write(path, arcname.as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        '-o', '--output-dir', type=Path, default=Path.cwd(),
        help='Directory to write the release zip into (default: current dir).')
    parser.add_argument(
        '--no-build', action='store_true',
        help='Skip the PyInstaller build and only zip an existing dist/daa_app.')
    parser.add_argument(
        'pyinstaller_args', nargs=argparse.REMAINDER,
        help='Extra args forwarded to PyInstaller (after "--").')
    args = parser.parse_args()

    version = read_version()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    zip_path = output_dir / f'daa_app_v.{version}.zip'

    print(f'[release] DAA app version {version}')
    if not args.no_build:
        # Drop a leading "--" separator if argparse kept it in REMAINDER.
        extra = [a for a in args.pyinstaller_args if a != '--']
        run_pyinstaller(extra)
    else:
        print('[release] --no-build: skipping PyInstaller, zipping existing bundle.')

    zip_bundle(zip_path)
    size_mb = zip_path.stat().st_size / (1024 * 1024)
    print(f'[release] done: {zip_path} ({size_mb:.1f} MiB)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
