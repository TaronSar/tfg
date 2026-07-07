"""Build an exclusion list of crops below a minimum size.

Instead of deleting or moving small crops (which would mutate the dataset and
change its hash on every run), this writes the offending crops' paths to a JSON
exclusion file. The dataset stays immutable; the training/eval dataset loader
skips the excluded crops as if they did not exist. This keeps the dataset hash
stable and avoids constant dataset churn.
"""
from __future__ import annotations

import json
from pathlib import Path

from PIL import Image

from src.uavid.common.constants import IMG_EXTS


def _shorter_side(path: Path) -> int | None:
    """Return the shorter side (px) of an image, or None if unreadable."""
    try:
        with Image.open(path) as im:
            return min(im.size)
    except Exception:
        return None


def build_exclusion(
    data_root: Path | str,
    min_px: int = 30,
    splits: tuple[str, ...] = ("train", "val"),
) -> dict:
    """Scan ``splits`` under ``data_root`` and list crops below ``min_px``.

    Enrollment images are deliberately never scanned -- they are the large
    support-domain views.

    Args:
        data_root: Dataset root containing the split subdirectories.
        min_px: Minimum allowed shorter-side size in pixels.
        splits: Splits to scan (default: train, val).

    Returns:
        A dict ``{"min_px", "splits", "data_root", "n_excluded", "excluded"}``
        where ``excluded`` is a sorted list of dataset-relative POSIX paths.
    """
    data_root = Path(data_root)
    excluded: list[str] = []
    checked = 0
    for split in splits:
        split_dir = data_root / split
        if not split_dir.is_dir():
            continue
        for path in sorted(split_dir.rglob("*")):
            if path.suffix.lower() not in IMG_EXTS:
                continue
            checked += 1
            side = _shorter_side(path)
            if side is not None and side < min_px:
                excluded.append(path.relative_to(data_root).as_posix())
    return {
        "min_px": min_px,
        "splits": list(splits),
        "data_root": str(data_root),
        "n_checked": checked,
        "n_excluded": len(excluded),
        "excluded": sorted(excluded),
    }


def write_exclusion(report: dict, out_path: Path | str) -> Path:
    """Write the exclusion report to ``out_path`` (parents created)."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2))
    return out_path


def load_excluded(exclude_json: Path | str) -> set[str]:
    """Load the set of excluded dataset-relative POSIX paths from a JSON file."""
    data = json.loads(Path(exclude_json).read_text())
    return set(data.get("excluded", []))
