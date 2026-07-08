r"""CLI: enroll a target into ``gallery.npy`` (client-side, privacy Option A).

Usage::

    PYTHONPATH=. uv run python scripts/enroll.py \\
        --images refs/ --out gallery.npy --checkpoint models/05_train/best.pth
"""

from __future__ import annotations

from pathlib import Path

import fire
from loguru import logger

from src.uavid.inference import enroll_gallery


def main(images: str, out: str = "gallery.npy", checkpoint: str | None = None) -> None:
    """Embed reference images and save the gallery.

    Args:
        images: Folder of the target's reference images (or a single image).
        out: Destination ``.npy`` path.
        checkpoint: Trained checkpoint (None -> zero-shot features).
    """
    emb = enroll_gallery(images, out=out, checkpoint=checkpoint)
    size_kb = Path(out).stat().st_size / 1024
    logger.info(f"Enrolled {emb.shape[0]} views -> {out}  shape={emb.shape}")
    logger.info(f"gallery.npy size: {size_kb:.1f} KB (the only artifact that leaves the client)")


if __name__ == "__main__":
    fire.Fire(main)
