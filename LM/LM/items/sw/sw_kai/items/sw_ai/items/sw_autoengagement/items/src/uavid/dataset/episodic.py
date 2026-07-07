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
from PIL import Image

from src.uavid.common.constants import IMG_EXTS


class IdentityIndex:
    """Scan ``data_root/<split>`` and index image paths per identity."""

    def __init__(self, root: str | Path,
                 exclude: set[str] | None = None,
                 exclude_root: str | Path | None = None) -> None:
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
        return (f"{len(self.names)} identities | images per identity: "
                f"min={min(counts)} max={max(counts)} total={sum(counts)}")


def load_image(path: Path, tfm) -> torch.Tensor:
    """Load ``path`` as RGB and apply transform ``tfm``."""
    with Image.open(path) as im:
        return tfm(im.convert("RGB"))


def sample_episode(index: IdentityIndex, tfm, n_way: int, k_shot: int,
                   q_query: int, support_index: IdentityIndex | None = None,
                   support_tfm=None):
    """Sample one N-way K-shot episode.

    When ``support_index`` is given, support images are drawn from that split
    (e.g. enrollment) and queries from ``index`` (e.g. operational train) --
    the mixed-domain episode that matches the deployment task.

    Args:
        index: Query-side identity index.
        tfm: Transform applied to query images.
        n_way: Number of classes per episode.
        k_shot: Support images per class.
        q_query: Query images per class.
        support_index: Optional support-side index for mixed-domain episodes.
        support_tfm: Transform for support images (defaults to ``tfm``).

    Returns:
        Tuple ``(support, support_labels, query, query_labels)`` of tensors.
    """
    if support_index is None:
        n_way = min(n_way, len(index))
        chosen = random.sample(index.names, n_way)
        s_imgs, s_lbls, q_imgs, q_lbls = [], [], [], []
        for c, name in enumerate(chosen):
            pool = index.identities[name]
            need = k_shot + q_query
            picks = (random.sample(pool, need) if len(pool) >= need
                     else random.choices(pool, k=need))
            for p in picks[:k_shot]:
                s_imgs.append(load_image(p, tfm))
                s_lbls.append(c)
            for p in picks[k_shot:]:
                q_imgs.append(load_image(p, tfm))
                q_lbls.append(c)
        return (torch.stack(s_imgs), torch.tensor(s_lbls),
                torch.stack(q_imgs), torch.tensor(q_lbls))

    support_tfm = support_tfm or tfm
    names = sorted(set(index.names) & set(support_index.names))
    if not names:
        raise RuntimeError(
            f"No overlapping identities between query split {index.root} "
            f"and support split {support_index.root}"
        )
    n_way = min(n_way, len(names))
    chosen = random.sample(names, n_way)
    s_imgs, s_lbls, q_imgs, q_lbls = [], [], [], []
    for c, name in enumerate(chosen):
        support_pool = support_index.identities[name]
        query_pool = index.identities[name]
        support_picks = (random.sample(support_pool, k_shot) if len(support_pool) >= k_shot
                         else random.choices(support_pool, k=k_shot))
        query_picks = (random.sample(query_pool, q_query) if len(query_pool) >= q_query
                       else random.choices(query_pool, k=q_query))
        for p in support_picks:
            s_imgs.append(load_image(p, support_tfm))
            s_lbls.append(c)
        for p in query_picks:
            q_imgs.append(load_image(p, tfm))
            q_lbls.append(c)
    return (torch.stack(s_imgs), torch.tensor(s_lbls),
            torch.stack(q_imgs), torch.tensor(q_lbls))
