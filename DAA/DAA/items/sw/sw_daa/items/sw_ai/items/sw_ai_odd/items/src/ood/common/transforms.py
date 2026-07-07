"""Image transforms and corruption utilities for the OOD pipeline."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import yaml
from torchvision import transforms as tv_transforms

_CONFIG_PATH = Path(__file__).parents[3] / "configs" / "dvc_config.yaml"


def _load_classes() -> list[str]:
    with open(_CONFIG_PATH, encoding="utf-8") as _f:
        return yaml.safe_load(_f)["dataset"]["classes"]


# ── Domain constants ──────────────────────────────────────────────────────────
CLASSES: list[str] = _load_classes()
CLASS_TO_IDX = {c: i for i, c in enumerate(CLASSES)}

IMAGENET_MEAN = (0.485, 0.456, 0.406)
IMAGENET_STD = (0.229, 0.224, 0.225)

IMG_SIZE = 224

_DARKEN_FACTORS = {1: 0.25, 2: 0.20, 3: 0.15, 4: 0.10, 5: 0.05}

CORRUPTIONS = [
    "fog",
    "snow",
    "frost",
    "brightness",
    "contrast",
    "defocus_blur",
    "motion_blur",
    "darken",
]

SEVERITIES = [1, 2, 3, 4, 5]


# ── Transforms ────────────────────────────────────────────────────────────────
def darken(img_np: np.ndarray, severity: int = 1) -> np.ndarray:
    """Custom 'darken' corruption: multiply pixel values by a severity factor.

    Args:
        img_np: uint8 RGB NumPy array to darken.
        severity: Severity level from 1 (least dark) to 5 (most dark).

    Returns:
        Darkened uint8 NumPy array of the same shape.
    """
    factor = _DARKEN_FACTORS.get(int(severity), 0.25)
    return np.clip(img_np.astype(np.float32) * factor, 0, 255).astype(np.uint8)



def make_train_transform(img_size: int = IMG_SIZE) -> tv_transforms.Compose:
    """Full preprocessing for training ID images (from raw AOT frames).

    Args:
        img_size: Target square side length in pixels.

    Returns:
        A ``tv_transforms.Compose`` pipeline with resize, greyscale,
        horizontal flip, tensor conversion and ImageNet normalisation.
    """
    return tv_transforms.Compose([
        tv_transforms.Resize((img_size, img_size)),
        tv_transforms.Grayscale(num_output_channels=3),
        tv_transforms.RandomHorizontalFlip(p=0.5),
        tv_transforms.ToTensor(),
        tv_transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


def make_eval_transform(img_size: int = IMG_SIZE) -> tv_transforms.Compose:
    """Full preprocessing for evaluation ID images (from raw AOT frames).

    Args:
        img_size: Target square side length in pixels.

    Returns:
        A ``tv_transforms.Compose`` pipeline identical to the training pipeline
        but without augmentation.
    """
    return tv_transforms.Compose([
        tv_transforms.Resize((img_size, img_size)),
        tv_transforms.Grayscale(num_output_channels=3),
        tv_transforms.ToTensor(),
        tv_transforms.Normalize(IMAGENET_MEAN, IMAGENET_STD),
    ])


#: Preprocessing for corrupted PNGs — identical pipeline to :func:`make_eval_transform`.
make_corrupted_transform = make_eval_transform
