"""Identity-folder dataset and episodic sampling for prototypical training.

Expected layout:
    data_root/
        train/
            identity_A/ img001.jpg ...
            identity_B/ ...
        val/
            identity_X/ ...

Each identity folder = one physical airframe (or one distinct model).
"""

import random
from pathlib import Path

import torch
from PIL import Image, ImageFilter
from torchvision import transforms

IMG_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

IMAGENET_MEAN = [0.485, 0.456, 0.406]
IMAGENET_STD  = [0.229, 0.224, 0.225]

# CLIP (OpenAI) visual encoder normalisation — different from ImageNet.
CLIP_MEAN = [0.48145466, 0.4578275,  0.40821073]
CLIP_STD  = [0.26862954, 0.26130258, 0.27577711]
# ---------------------------------------------------------------------------
# Module-level image cache — populated by preload_images() before training.
# ---------------------------------------------------------------------------
_IMAGE_CACHE: dict = {}


def preload_images(*indices) -> None:
    """Preload all images from the given IdentityIndex objects into RAM.

    Eliminates per-file NAS open latency. The dataset is typically only a few
    MB of small JPEG crops and fits comfortably in RAM.  Safe to call multiple
    times; already-cached paths are skipped.
    """
    from pathlib import Path as _Path
    all_paths: set = set()
    for index in indices:
        for imgs in index.identities.values():
            all_paths.update(imgs)
    to_load = all_paths - _IMAGE_CACHE.keys()
    if not to_load:
        return
    print(f"Preloading {len(to_load)} images into RAM...")
    for p in to_load:
        with Image.open(p) as im:
            _IMAGE_CACHE[p] = im.convert("RGB").copy()
    print(f"  cached {len(_IMAGE_CACHE)} images total")

class DegradeToOperational:
    """Simulate the operational pixel envelope.

    Downscales the image so its longer side lands in [min_px, max_px]
    (default U(46,143), the 50-100 m / 1080p / 30-45deg HFOV envelope),
    optionally blurs, then resizes back up to the model input size.
    Destroys fine texture exactly like a distant detector crop does.
    """

    def __init__(self, p: float = 0.5, min_px: int = 46, max_px: int = 143,
                 blur_p: float = 0.3):
        self.p = p
        self.min_px = min_px
        self.max_px = max_px
        self.blur_p = blur_p

    def __call__(self, img: Image.Image) -> Image.Image:
        if random.random() > self.p:
            return img
        target = random.randint(self.min_px, self.max_px)
        w, h = img.size
        scale = target / max(w, h)
        if scale < 1.0:
            img = img.resize((max(1, int(w * scale)), max(1, int(h * scale))),
                             Image.BILINEAR)
            if random.random() < self.blur_p:
                img = img.filter(ImageFilter.GaussianBlur(radius=random.uniform(0.3, 1.0)))
        return img


def build_transform(
    image_size: int = 224,
    train: bool = True,
    degrade_p: float = 0.0,
    degrade_min_px: int = 46,
    degrade_max_px: int = 143,
    mean=None,
    std=None,
) -> transforms.Compose:
    """Build the image pre-processing pipeline.

    degrade_p > 0 applies DegradeToOperational regardless of *train*, so
    evaluation at the operational sensor envelope is also supported.
    mean / std default to ImageNet values; pass CLIP_MEAN / CLIP_STD for
    CLIP-based backbones.
    """
    if mean is None:
        mean = IMAGENET_MEAN
    if std is None:
        std = IMAGENET_STD
    ops = []
    if degrade_p > 0:
        ops.append(DegradeToOperational(p=degrade_p,
                                        min_px=degrade_min_px,
                                        max_px=degrade_max_px))
    if train:
        ops += [
            transforms.Resize((image_size, image_size)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(brightness=0.3, contrast=0.3, saturation=0.2),
        ]
    else:
        ops.append(transforms.Resize((image_size, image_size)))
    ops += [
        transforms.ToTensor(),
        transforms.Normalize(mean, std),
    ]
    return transforms.Compose(ops)


class IdentityIndex:
    """Scans data_root/<split> and indexes images per identity."""

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self.identities: dict[str, list[Path]] = {}
        for ident_dir in sorted(p for p in self.root.iterdir() if p.is_dir()):
            imgs = sorted(
                f for f in ident_dir.rglob("*") if f.suffix.lower() in IMG_EXTS
            )
            if len(imgs) >= 2:
                self.identities[ident_dir.name] = imgs
        self.names = list(self.identities.keys())
        if not self.names:
            raise RuntimeError(f"No identity folders with >=2 images under {self.root}")

    def __len__(self):
        return len(self.names)

    def stats(self) -> str:
        counts = [len(v) for v in self.identities.values()]
        return (f"{len(self.names)} identities | images per identity: "
                f"min={min(counts)} max={max(counts)} total={sum(counts)}")


def load_image(path: Path, tfm) -> torch.Tensor:
    if path in _IMAGE_CACHE:
        return tfm(_IMAGE_CACHE[path])
    with Image.open(path) as im:
        return tfm(im.convert("RGB"))


def sample_episode(index: IdentityIndex, tfm, n_way: int, k_shot: int,
                   q_query: int, support_index: IdentityIndex | None = None,
                   support_tfm=None,
                   hard_negatives=None, hard_negative_p: float = 0.5):
    """Returns support (N*K,C,H,W), support_labels, query (N*Q,C,H,W), query_labels.

    Phase-2 hard-negative mining: when hard_negatives is set, with probability
    hard_negative_p at least 2 of the listed identities (present in the index)
    are guaranteed to co-occur in the episode.
    """
    hard_negatives = hard_negatives or []

    def _choose_with_hard(pool, n):
        valid_hard = [x for x in hard_negatives if x in pool]
        if len(valid_hard) >= 2 and random.random() < hard_negative_p:
            forced = random.sample(valid_hard, min(2, len(valid_hard), n))
            rest_pool = [x for x in pool if x not in forced]
            n_rest = max(0, n - len(forced))
            rest = (random.sample(rest_pool, n_rest)
                    if len(rest_pool) >= n_rest else rest_pool)
            return forced + rest
        return random.sample(pool, min(n, len(pool)))

    if support_index is None:
        n_way = min(n_way, len(index))
        chosen = _choose_with_hard(index.names, n_way)
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
    chosen = _choose_with_hard(names, n_way)
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
