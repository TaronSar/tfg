"""Path utilities for AOT dataset frames and detection crops."""
from __future__ import annotations

import re
from pathlib import Path, PurePosixPath

# Captures the ``_x_<X>_y_<Y>`` crop-offset suffix appended by the
# detection pipeline.  The groups are optional — use the non-capturing
# helpers (``crop_to_frame_path``) when offsets are not needed, and
# ``parse_crop_offset`` when they are.
CROP_OFFSET_RE = re.compile(r"_x_(\d+)_y_(\d+)$")


def crop_to_frame_path(crop_file_name: str) -> str:
    """Recover the original AOT frame path from a detection crop file_name.

    Detection crops are named
    ``<part>/Images/<flight_id>/<stem>_x_<X>_y_<Y>.png``.  The original
    frame is ``<part>/Images/<flight_id>/<stem>.png``.

    Args:
        crop_file_name: Crop ``file_name`` field from a COCO JSON image
            entry (e.g. ``"part1/Images/abc/tsabc_x_1440_y_0.png"``).

    Returns:
        AOT-relative path to the original uncropped frame, preserving the
        input file extension.
    """
    p = PurePosixPath(crop_file_name)
    return str(p.parent / f"{CROP_OFFSET_RE.sub('', p.stem)}{p.suffix}")


def parse_crop_offset(file_name: str) -> tuple[int, int]:
    """Extract ``(x0, y0)`` pixel offset from a detection crop filename.

    Args:
        file_name: COCO ``file_name`` such as
            ``"part1/Images/abc/tsabc_x_1440_y_0.png"``.

    Returns:
        ``(x0, y0)`` integer tuple.

    Raises:
        ValueError: If the ``_x_<X>_y_<Y>`` suffix is not found.
    """
    stem = PurePosixPath(file_name).stem
    m = CROP_OFFSET_RE.search(stem)
    if not m:
        raise ValueError(f"Cannot parse crop offset from {file_name!r}")
    return int(m.group(1)), int(m.group(2))


def parse_frame_path(path: str) -> tuple[str, str, str]:
    """Extract ``(flight_id, img_name, part)`` from an AOT-relative path.

    Given ``"part1/Images/<flight_id>/<img_name>"`` returns
    ``(flight_id, img_name, "part1")``.

    Args:
        path: AOT-relative frame path with the structure
            ``"<part>/Images/<flight_id>/<img_name>"``.

    Returns:
        A 3-tuple ``(flight_id, img_name, part)``.
    """
    p = PurePosixPath(path)
    return p.parent.name, p.name, p.parts[0]


def image_path(flight_id: str, img_name: str, part: str, aot_root: Path) -> Path:
    """Return the absolute path to an AOT frame on the NAS.

    Args:
        flight_id: Flight identifier (may contain ``__part`` suffix for
            collision resolution).
        img_name: Frame filename (e.g. ``"<timestamp><fid>.png"``).
        part: Dataset part string.
        aot_root: Root path to the AOT dataset.

    Returns:
        Absolute ``Path`` to the frame image.
    """
    real_fid = flight_id.split("__")[0]
    return aot_root / part / "Images" / real_fid / img_name


def relative_path(flight_id: str, img_name: str, part: str) -> str:
    """Return the relative path to an AOT frame inside *aot_root*.

    Args:
        flight_id: Flight identifier (may contain ``__part`` suffix).
        img_name: Frame filename.
        part: Dataset part string.

    Returns:
        Forward-slash-separated relative path string, e.g.
        ``"part1/Images/<real_fid>/<img_name>"``.
    """
    real_fid = flight_id.split("__")[0]
    return f"{part}/Images/{real_fid}/{img_name}"
