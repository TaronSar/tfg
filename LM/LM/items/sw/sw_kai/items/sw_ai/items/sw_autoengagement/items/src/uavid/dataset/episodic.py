"""Identity-folder dataset and episodic sampling for prototypical training.

Expected layout::

    data_root/
        train/      identity_A/ img001.jpg ...
        val/        identity_X/ ...
        enrollment/ identity_A/ ...   # optional, for mixed-domain support

Each identity folder is one physical airframe (or one distinct model). Folders
whose names start with ``neg_`` are train-only hard negatives.
"""

from __future__ import annotations

import random
from pathlib import Path

import torch
from loguru import logger
from PIL import Image

from src.uavid.common.constants import IMG_EXTS

# ---------------------------------------------------------------------------
# Module-level image cache — populated by preload_images() before training.
# Eliminates per-file NAS open latency: the dataset is typically only a few
# MB of small JPEG crops and fits comfortably in RAM.
# ---------------------------------------------------------------------------
_IMAGE_CACHE: dict[Path, Image.Image] = {}


def preload_images(*indices: IdentityIndex) -> None:
    """Preload all images from the given indices into RAM.

    Call once before training to trade a few seconds of startup time for
    zero per-file I/O latency during all subsequent episodes.  Safe to call
    multiple times; already-cached images are skipped.

    Args:
        *indices: One or more :class:`IdentityIndex` objects whose images
            should be loaded into the module-level cache.
    """
    all_paths: set[Path] = set()
    for index in indices:
        for imgs in index.identities.values():
            all_paths.update(imgs)
    to_load = all_paths - _IMAGE_CACHE.keys()
    if not to_load:
        return
    logger.info(f"Preloading {len(to_load)} images into RAM...")
    for p in to_load:
        with Image.open(p) as im:
            _IMAGE_CACHE[p] = im.convert("RGB").copy()
    logger.info(f"  cached {len(_IMAGE_CACHE)} images total")


class IdentityIndex:
    """Scan ``data_root/<split>`` and index image paths per identity."""

    def __init__(
        self,
        root: str | Path,
        exclude: set[str] | None = None,
        exclude_root: str | Path | None = None,
    ) -> None:
        """Index every identity folder under ``root`` with >= 2 images.

        Args:
            root: Path to a split directory (e.g. ``data_root/train``).
            exclude: Optional set of dataset-relative POSIX paths to skip
                (the small-crop exclusion list). Paths are relative to
                ``exclude_root`` (defaults to ``root.parent``, i.e. the dataset
                root), matching what ``filter_crops.build_exclusion`` writes.
            exclude_root: Root the ``exclude`` paths are relative to.

        Raises:
            RuntimeError: If no identity folder with >= 2 images is found.
        """
        self.root = Path(root)
        exclude = exclude or set()
        ex_root = Path(exclude_root) if exclude_root is not None else self.root.parent
        self.identities: dict[str, list[Path]] = {}
        for ident_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            imgs = []
            for f in sorted(ident_dir.rglob("*")):
                if f.suffix.lower() not in IMG_EXTS:
                    continue
                if exclude:
                    try:
                        rel = f.relative_to(ex_root).as_posix()
                    except ValueError:
                        rel = None
                    if rel in exclude:
                        continue
                imgs.append(f)
            if len(imgs) >= 2:
                self.identities[ident_dir.name] = imgs
        self.names = list(self.identities.keys())
        if not self.names:
            raise RuntimeError(f"No identity folders with >=2 images under {self.root}")

    def __len__(self) -> int:
        return len(self.names)

    def stats(self) -> str:
        """Return a human-readable summary of identity/image counts."""
        counts = [len(v) for v in self.identities.values()]
        return (
            f"{len(self.names)} identities | images per identity: "
            f"min={min(counts)} max={max(counts)} total={sum(counts)}"
        )


def load_image(path: Path, tfm) -> torch.Tensor:
    """Load ``path`` as RGB and apply transform ``tfm``.

    Returns the cached PIL image when :func:`preload_images` has been called,
    otherwise falls back to opening the file from disk.

    Args:
        path: Path to the image file.
        tfm: Torchvision transform to apply after loading.

    Returns:
        Transformed image tensor of shape ``(C, H, W)``.
    """
    if path in _IMAGE_CACHE:
        return tfm(_IMAGE_CACHE[path])
    with Image.open(path) as im:
        return tfm(im.convert("RGB"))


def sample_episode(
    index: IdentityIndex,
    tfm,
    n_way: int,
    k_shot: int,
    q_query: int,
    support_index: IdentityIndex | None = None,
    support_tfm=None,
    hard_negatives: list[str] | None = None,
    hard_negative_p: float = 0.5,
):
    """Sample one N-way K-shot episode.

    When ``support_index`` is given, support images are drawn from that split
    (e.g. enrollment) and queries from ``index`` (e.g. operational train) --
    the mixed-domain episode that matches the deployment task.

    Phase-2 hard-negative mining: when ``hard_negatives`` is set, with
    probability ``hard_negative_p`` at least 2 of the listed identities
    (those present in the index) are guaranteed to co-occur in the episode.
    This forces the model to regularly discriminate its hardest confusable
    pairs instead of only seeing easy random N-way combinations.

    Args:
        index: Query-side identity index.
        tfm: Transform applied to query images.
        n_way: Number of classes per episode.
        k_shot: Support images per class.
        q_query: Query images per class.
        support_index: Optional support-side index for mixed-domain episodes.
        support_tfm: Transform for support images (defaults to ``tfm``).
        hard_negatives: Identity names to force into hard-negative episodes.
        hard_negative_p: Fraction of episodes that are hard-negative episodes.

    Returns:
        Tuple ``(support, support_labels, query, query_labels)`` of tensors.
    """
    hard_negatives = hard_negatives or []

    def _choose_with_hard(pool: list[str], n: int) -> list[str]:
        """Sample n identities, guaranteeing hard-negative co-occurrence."""
        valid_hard = [x for x in hard_negatives if x in pool]
        if len(valid_hard) >= 2 and random.random() < hard_negative_p:
            forced = random.sample(valid_hard, min(2, len(valid_hard), n))
            rest_pool = [x for x in pool if x not in forced]
            n_rest = max(0, n - len(forced))
            rest = random.sample(rest_pool, n_rest) if len(rest_pool) >= n_rest else rest_pool
            return forced + rest
        return random.sample(pool, min(n, len(pool)))

    if support_index is None:
        n_way = min(n_way, len(index))
        chosen = _choose_with_hard(index.names, n_way)
        s_imgs, s_lbls, q_imgs, q_lbls = [], [], [], []
        for c, name in enumerate(chosen):
            pool = index.identities[name]
            need = k_shot + q_query
            picks = random.sample(pool, need) if len(pool) >= need else random.choices(pool, k=need)
            for p in picks[:k_shot]:
                s_imgs.append(load_image(p, tfm))
                s_lbls.append(c)
            for p in picks[k_shot:]:
                q_imgs.append(load_image(p, tfm))
                q_lbls.append(c)
        return (
            torch.stack(s_imgs),
            torch.tensor(s_lbls),
            torch.stack(q_imgs),
            torch.tensor(q_lbls),
        )

    support_tfm = support_tfm or tfm
    names = sorted(set(index.names) & set(support_index.names))
    if not names:
        raise RuntimeError(
            f"No overlapping identities between query split {index.root} "
            f"and support split {support_index.root}"
        )
    n_way = min(n_way, len(names))
    chosen = _choose_with_hard(names, n_way)
    s_imgs, s_lbls, q_imgs, q_lbls = [], [], [], []
    for c, name in enumerate(chosen):
        support_pool = support_index.identities[name]
        query_pool = index.identities[name]
        support_picks = (
            random.sample(support_pool, k_shot)
            if len(support_pool) >= k_shot
            else random.choices(support_pool, k=k_shot)
        )
        query_picks = (
            random.sample(query_pool, q_query)
            if len(query_pool) >= q_query
            else random.choices(query_pool, k=q_query)
        )
        for p in support_picks:
            s_imgs.append(load_image(p, support_tfm))
            s_lbls.append(c)
        for p in query_picks:
            q_imgs.append(load_image(p, tfm))
            q_lbls.append(c)
    return (torch.stack(s_imgs), torch.tensor(s_lbls), torch.stack(q_imgs), torch.tensor(q_lbls))
