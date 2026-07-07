"""Project-wide constants for the few-shot UAV identification pipeline."""
from __future__ import annotations

# Image file extensions recognised when scanning identity folders.
IMG_EXTS: frozenset[str] = frozenset({".jpg", ".jpeg", ".png", ".bmp", ".webp"})

# ImageNet normalisation statistics (MobileNetV3-Small / DINOv2 are ImageNet-pretrained).
IMAGENET_MEAN: tuple[float, float, float] = (0.485, 0.456, 0.406)
IMAGENET_STD: tuple[float, float, float] = (0.229, 0.224, 0.225)

# CLIP (OpenAI) visual encoder normalisation — different from ImageNet.
CLIP_MEAN: tuple[float, float, float] = (0.48145466, 0.4578275,  0.40821073)
CLIP_STD:  tuple[float, float, float] = (0.26862954, 0.26130258, 0.27577711)

