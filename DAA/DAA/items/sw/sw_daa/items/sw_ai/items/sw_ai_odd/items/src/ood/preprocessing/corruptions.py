"""Image corruption utilities for the OOD pipeline."""
from __future__ import annotations

import tempfile
import warnings
from pathlib import Path, PurePosixPath

import numpy as np
from loguru import logger
from PIL import Image

from src.ood.common.transforms import darken

# Suppress the pkg_resources deprecation warning emitted by imagecorruptions
# at import time in the main process.
warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)


def _worker_init() -> None:
    """Targeted warning filter for loky worker processes.

    ``loky`` workers inherit environment variables but *not* the in-process
    ``warnings`` filter registry, so the filter above would be lost in
    workers.  Passing this function as ``initializer=`` to
    ``joblib.Parallel`` re-applies only the specific filter we need without
    silencing all ``UserWarning``s globally via ``PYTHONWARNINGS``.
    """
    warnings.filterwarnings("ignore", message="pkg_resources is deprecated", category=UserWarning)

# TODO: Remove these shims if imagecorruptions is updated to support NumPy >= 2.
# NumPy >= 2 shims for imagecorruptions (must run before the import below)
for _alias, _target in (
    ("float_", np.float64),
    ("int", int),
    ("bool", bool),
    ("complex_", np.complex128),
):
    if not hasattr(np, _alias):
        setattr(np, _alias, _target)

# imagecorruptions does `from pkg_resources import resource_filename` at import
# time to locate its bundled frost PNG textures.  In some uv/setuptools
# configurations pkg_resources is not importable even when setuptools is
# installed.  We provide a minimal stub that resolves paths correctly via
# importlib so that frost (and other texture-based corruptions) work.
try:
    import pkg_resources  # noqa: F401
except (ModuleNotFoundError, ImportError):
    import importlib.util as _ilu
    import os as _os
    import sys as _sys
    import types as _types

    _pkg = _types.ModuleType("pkg_resources")

    def _resource_filename(package_or_requirement: str, resource_name: str) -> str:
        spec = _ilu.find_spec(package_or_requirement)
        if spec and spec.origin:
            return _os.path.join(_os.path.dirname(spec.origin), resource_name)
        return resource_name

    _pkg.resource_filename = _resource_filename  # type: ignore[attr-defined]
    _sys.modules["pkg_resources"] = _pkg

from imagecorruptions import corrupt  # noqa: E402


def _save_rgb_png_atomic(image: Image.Image, out_path: Path) -> None:
    """Save a PNG atomically to reduce risk of truncated files on NAS."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            suffix=out_path.suffix,
            prefix=f".{out_path.stem}.",
            dir=out_path.parent,
            delete=False,
        ) as tmp:
            tmp_name = tmp.name
        image.save(tmp_name)
        Path(tmp_name).replace(out_path)
    finally:
        if tmp_name is not None:
            tmp_path = Path(tmp_name)
            if tmp_path.exists():
                tmp_path.unlink()


def _is_valid_image(path: Path) -> bool:
    """Return ``True`` when *path* exists and can be fully decoded."""
    if not path.exists() or not path.is_file():
        return False
    try:
        with Image.open(path) as img:
            img.load()
        return True
    except OSError:
        return False


def _save_verified_rgb_png(
    image: Image.Image,
    out_path: Path,
    *,
    max_attempts: int = 5,
) -> bool:
    """Save PNG atomically and verify readability, retrying on corruption."""
    for attempt in range(1, max_attempts + 1):
        _save_rgb_png_atomic(image, out_path)
        if _is_valid_image(out_path):
            return True
        logger.warning(
            f"Corrupted write detected for {out_path} (attempt {attempt}/{max_attempts}); retrying"
        )
        try:
            out_path.unlink(missing_ok=True)
        except OSError:
            pass
    return False


def preprocess_for_corruption(img_path: Path) -> np.ndarray:
    """Load an AOT frame and return it as a uint8 RGB array (original resolution).

    Args:
        img_path: Absolute path to the source frame image.

    Returns:
        uint8 NumPy array with shape ``(H, W, 3)``.
    """
    img = Image.open(img_path).convert("RGB")
    return np.array(img, dtype=np.uint8)


def apply_corruption(arr: np.ndarray, corruption_name: str, severity: int) -> np.ndarray:
    """Apply a single named corruption at a given severity.

    Args:
        arr: uint8 RGB NumPy array to corrupt.
        corruption_name: Name of the corruption (must be in ``CORRUPTIONS`` or
            ``"darken"`` for the custom darkening function).
        severity: Severity level between 1 and 5 inclusive.

    Returns:
        Corrupted uint8 NumPy array of the same shape.
    """
    if corruption_name == "darken":
        return darken(arr, severity=severity)
    return corrupt(arr, corruption_name=corruption_name, severity=severity)


def corrupted_full_path(
    frame_rel: str,
    corruption_name: str,
    severity: int,
    corrupted_full_img_dir: Path,
) -> Path:
    """Build the path for a corrupted full-size frame.

    Mirrors the AOT layout and appends a ``_<type>_<sev>`` suffix to the stem
    so the layout is split-independent::

        <corrupted_full_img_dir>/<part>/Images/<flight>/<frame_stem>_<type>_<sev>.png

    Args:
        frame_rel: AOT-relative frame path (``<part>/Images/<flight>/<frame>``).
        corruption_name: Corruption type name.
        severity: Severity level.
        corrupted_full_img_dir: Root of the corrupted full-image tree.

    Returns:
        Absolute ``Path`` to the corrupted full frame.
    """
    p = PurePosixPath(frame_rel)
    return corrupted_full_img_dir / p.parent / f"{p.stem}_{corruption_name}_{severity}{p.suffix}"


def corrupted_crop_rel(crop_file_name: str, corruption_name: str, severity: int) -> str:
    """Build the storage-relative path for a corrupted crop.

    The clean crop ``file_name`` already encodes the ``_x_<X>_y_<Y>`` offset;
    the corrupted variant appends ``_<type>_<sev>`` to the stem.

    Args:
        crop_file_name: Clean crop ``file_name`` (relative to the clean crops
            root), e.g. ``"part1/Images/abc/ts_x_1440_y_0.png"``.
        corruption_name: Corruption type name.
        severity: Severity level.

    Returns:
        Forward-slash-separated storage-relative path for the corrupted crop.
    """
    p = PurePosixPath(crop_file_name)
    return str(p.parent / f"{p.stem}_{corruption_name}_{severity}{p.suffix}")


def process_single_image(
    rec: dict,
    corruption_name: str,
    corrupted_full_img_dir: Path,
    aot_root: Path,
    severities: list[int],
) -> list[dict]:
    """Apply *corruption_name* at every severity, save PNGs, return records.

    Each severity level produces one full-size corrupted PNG at
    :func:`corrupted_full_path`.  Images that already exist on disk are skipped
    to avoid redundant reprocessing.  The function is designed to be called
    from a ``joblib.Parallel`` worker.

    Args:
        rec: Source JSONL record with fields ``path``, ``img_name``, ``label``,
            ``time``, and ``flight_id``.
        corruption_name: Name of the corruption to apply.
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        aot_root: Root path to the AOT dataset.
        severities: List of severity levels to apply (e.g. ``[1, 2, 3, 4, 5]``).

    Returns:
        List of JSONL records (one per severity level) with fields
        ``img_name``, ``type``, ``severity``, ``label``, ``time``,
        ``flight_id``, and ``path`` (the AOT-relative source frame path, which
        also locates the corrupted file).  Returns an empty list if the
        source image is not found on disk.
    """
    specs = [
        (
            sev,
            corrupted_full_path(rec["path"], corruption_name, sev, corrupted_full_img_dir),
            {
                "img_name": rec["img_name"],
                "type": corruption_name,
                "severity": sev,
                "label": rec["label"],
                "time": rec["time"],
                "flight_id": rec["flight_id"],
                "path": rec["path"],
            },
        )
        for sev in severities
    ]

    if all(_is_valid_image(out_path) for _, out_path, _ in specs):
        return [record for _, _, record in specs]

    img_path = aot_root / rec["path"]
    if not img_path.exists():
        return []

    arr: np.ndarray | None = None
    written_records: list[dict] = []

    for severity, out_path, record in specs:
        if _is_valid_image(out_path):
            written_records.append(record)
            continue

        if out_path.exists():
            logger.warning(f"Invalid corrupted full frame found, regenerating: {out_path}")
            try:
                out_path.unlink(missing_ok=True)
            except OSError:
                pass

        if arr is None:
            arr = preprocess_for_corruption(img_path)

        corrupted = apply_corruption(arr, corruption_name, severity)
        # Save as greyscale (3-channel with equal channels) since AOT
        # source frames are inherently greyscale — colour artefacts from
        # snow/frost/fog would be semantically misleading.
        ok = _save_verified_rgb_png(
            Image.fromarray(corrupted).convert("L").convert("RGB"),
            out_path,
        )
        if ok:
            written_records.append(record)
        else:
            logger.warning(
                f"Failed to write a valid corrupted full frame after retries: {out_path}"
            )

    return written_records
