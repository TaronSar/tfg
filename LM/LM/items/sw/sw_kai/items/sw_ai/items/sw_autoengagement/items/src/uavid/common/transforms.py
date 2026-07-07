"""Image transforms: operational degradation and the encoder input pipeline."""
from __future__ import annotations

import random

from PIL import Image, ImageFilter
from torchvision import transforms

from src.uavid.common.constants import IMAGENET_MEAN, IMAGENET_STD, CLIP_MEAN, CLIP_STD  # noqa: F401


class DegradeToOperational:
    """Simulate the operational pixel envelope of a distant detector crop.

    Downscales the image so its longer side lands in ``[min_px, max_px]``
    (default ``U(46, 143)`` -- the 50-100 m / 1080p / 30-45 deg HFOV envelope),
    optionally blurs, then upscales back to the model input size. This destroys
    fine texture exactly like a far-away crop does.
    """

    def __init__(self, p: float = 0.5, min_px: int = 46, max_px: int = 143,
                 blur_p: float = 0.3) -> None:
        """Initialise the degradation transform.

        Args:
            p: Probability of applying degradation to a given image.
            min_px: Minimum longer-side size (px) of the downscaled image.
            max_px: Maximum longer-side size (px) of the downscaled image.
            blur_p: Probability of an additional Gaussian blur when degrading.
        """
        self.p = p
        self.min_px = min_px
        self.max_px = max_px
        self.blur_p = blur_p

    def __call__(self, img: Image.Image) -> Image.Image:
        """Apply the (stochastic) degradation to ``img`` and return it."""
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
    mean: tuple | list | None = None,
    std: tuple | list | None = None,
) -> transforms.Compose:
    """Build the torchvision transform pipeline for the encoder.

    Args:
        image_size: Square input resolution (px) fed to the encoder.
        train: If True, apply training augmentations (flip, colour jitter).
        degrade_p: Probability of operational degradation.  Applies in both
            train and eval modes so Phase-0 evaluation at the sensor envelope
            is supported (set to 1.0 to always degrade).
        degrade_min_px: Shorter-side floor for the downscaled image (px).
        degrade_max_px: Shorter-side ceiling for the downscaled image (px).
        mean: Per-channel mean for normalisation (defaults to ImageNet).
        std: Per-channel std for normalisation (defaults to ImageNet).

    Returns:
        A composed transform mapping a PIL image to a normalised tensor.
    """
    if mean is None:
        mean = IMAGENET_MEAN
    if std is None:
        std = IMAGENET_STD
    ops: list = []
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
