"""Build a small dataset manifest (counts only) used as a DVC stage output.

Image datasets live on the NAS and are never copied into git/dvc-storage; each
data-generation stage instead emits this tiny JSON manifest (per-split identity
and image counts) as its tracked ``out``, mirroring how ``sw_ai_detection`` keeps
the heavy images on the NAS and tracks only small derived artifacts.
"""

from __future__ import annotations

import json
from pathlib import Path

from src.uavid.common.constants import IMG_EXTS


def build_manifest(
    data_root: Path | str, splits: tuple[str, ...] = ("train", "val", "enrollment")
) -> dict:
    """Summarise identity/image counts per split under ``data_root``.

    Args:
        data_root: Dataset root containing the split subdirectories.
        splits: Splits to summarise.

    Returns:
        A dict with ``data_root`` and a per-split ``{n_identities, n_images}``.
    """
    data_root = Path(data_root)
    summary: dict = {"data_root": str(data_root), "splits": {}}
    for split in splits:
        split_dir = data_root / split
        if not split_dir.is_dir():
            continue
        idents = [p for p in split_dir.iterdir() if p.is_dir()]
        n_imgs = sum(1 for d in idents for f in d.rglob("*") if f.suffix.lower() in IMG_EXTS)
        summary["splits"][split] = {"n_identities": len(idents), "n_images": n_imgs}
    return summary


def write_manifest(
    data_root: Path | str,
    out_path: Path | str,
    splits: tuple[str, ...] = ("train", "val", "enrollment"),
) -> Path:
    """Build the manifest for ``data_root`` and write it to ``out_path``.

    Args:
        data_root: Dataset root containing the split subdirectories.
        out_path: Destination JSON path (parent dirs created if needed).
        splits: Splits to summarise.

    Returns:
        Resolved path of the written manifest file.
    """
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(build_manifest(data_root, splits), indent=2))
    return out_path
