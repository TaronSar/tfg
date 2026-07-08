"""Episodic few-shot dataset and N-way K-shot samplers (mixed-domain support)."""

from src.uavid.dataset.episodic import (
    IdentityIndex,
    load_image,
    preload_images,
    sample_episode,
)

__all__ = [
    "IdentityIndex",
    "load_image",
    "preload_images",
    "sample_episode",
]
