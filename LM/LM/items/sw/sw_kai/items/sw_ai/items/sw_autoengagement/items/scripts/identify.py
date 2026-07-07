"""CLI: identify query images against an enrolled gallery.

Usage::

    PYTHONPATH=. uv run python scripts/identify.py \\
        --gallery gallery.npy --images crops/ --threshold 0.6 \\
        --checkpoint models/05_train/best.pth
"""
from __future__ import annotations

import fire
import numpy as np
from loguru import logger

from src.uavid.inference import identify_paths


def main(gallery: str, images: str, checkpoint: str | None = None,
         threshold: float = 0.6) -> None:
    """Score query images and print per-image verdicts plus a summary.

    Args:
        gallery: Path to the enrolled ``gallery.npy``.
        images: Query image or folder.
        checkpoint: Trained checkpoint (None -> zero-shot features).
        threshold: Score at/above which a query is declared ``MATCH``.
    """
    results = identify_paths(gallery, images, checkpoint=checkpoint, threshold=threshold)
    for path, score, verdict in results:
        logger.info(f"{str(path)[-50:]:<50} {score:>8.4f}  {verdict}")
    scores = np.array([s for _, s, _ in results])
    matches = int((scores >= threshold).sum())
    logger.info(f"queries: {len(scores)} | mean {scores.mean():.4f} | "
                f"min {scores.min():.4f} | max {scores.max():.4f} | "
                f"matches @ {threshold}: {matches}")


if __name__ == "__main__":
    fire.Fire(main)
