r"""CLI: write a small dataset manifest JSON (a DVC stage stamp output).

Usage::

    PYTHONPATH=. uv run python scripts/dataset_manifest.py \\
        --data_root /mnt/Pool_IA/IA_Dataset/.../uav_renders \\
        --out data/manifests/00_render.json
"""

from __future__ import annotations

import fire
from loguru import logger

from src.uavid.preprocessing.manifest import write_manifest


def main(data_root: str, out: str, splits: str = "train,val,enrollment") -> None:
    """Write the per-split count manifest for ``data_root`` to ``out``.

    Args:
        data_root: Dataset root containing the split subdirectories.
        out: Destination JSON path for the manifest.
        splits: Comma-separated splits to summarise.
    """
    split_tuple = tuple(s.strip() for s in splits.split(",") if s.strip())
    path = write_manifest(data_root, out, split_tuple)
    logger.info(f"Wrote dataset manifest -> {path}")


if __name__ == "__main__":
    fire.Fire(main)
