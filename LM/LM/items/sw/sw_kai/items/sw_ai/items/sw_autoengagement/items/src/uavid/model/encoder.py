"""Encoder backbones for few-shot UAV identification.

Supported backbones (``--backbone`` in scripts/train.py)::

    mobilenetv3    MobileNetV3-Small + projection head  (original TFG/KAI config)
    dinov2_vits14  DINOv2 ViT-S/14 (384-d) + projection head
    dinov2_vitb14  DINOv2 ViT-B/14 (768-d) + projection head
    clip_vit_b32   OpenAI CLIP ViT-B/32 (512-d visual) + projection head

All encoders expose ``.features`` (backbone) and ``.head`` (projection) for the
two-LR AdamW optimiser in trainer.py.  Use ``build_encoder()`` as the factory.
``BACKBONE_NORM`` maps backbone name -> ``(mean, std)`` for ``build_transform()``.
"""
from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

# Per-backbone input normalisation constants.
# Keep in sync with src/uavid/common/constants.py.
BACKBONE_NORM: dict[str, tuple[list[float], list[float]]] = {
    "mobilenetv3":   ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    "dinov2_vits14": ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    "dinov2_vitb14": ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    "clip_vit_b32":  ([0.48145466, 0.4578275, 0.40821073],
                      [0.26862954, 0.26130258, 0.27577711]),
}


class ProtoNetEncoder(nn.Module):
    """MobileNetV3-Small backbone + 128-d L2-normalised projection head."""

    def __init__(self, embed_dim: int = 128, pretrained: bool = True,
                 l2_normalize: bool = True) -> None:
        """Initialise the encoder.

        Args:
            embed_dim: Output embedding dimensionality.
            pretrained: Load ImageNet-pretrained backbone weights.
            l2_normalize: L2-normalise the output embedding onto the unit sphere.
        """
        super().__init__()
        weights = (
            torchvision.models.MobileNet_V3_Small_Weights.IMAGENET1K_V1
            if pretrained
            else None
        )
        backbone = torchvision.models.mobilenet_v3_small(weights=weights)
        self.features = backbone.features        # -> (B, 576, H/32, W/32)
        self.avgpool = backbone.avgpool          # -> (B, 576, 1, 1)
        self.head = nn.Sequential(
            nn.Flatten(1),
            nn.Linear(576, embed_dim),
            nn.LayerNorm(embed_dim),
        )
        self.embed_dim = embed_dim
        self.l2_normalize = l2_normalize

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Embed a batch of images into the (optionally L2-normalised) space."""
        x = self.features(x)
        x = self.avgpool(x)
        x = self.head(x)
        if self.l2_normalize:
            x = F.normalize(x, p=2, dim=-1)
        return x


# ---------------------------------------------------------------------------
# DINOv2 encoder (Phase 1 — no hardware constraints)
# ---------------------------------------------------------------------------

class DinoV2Encoder(nn.Module):
    """DINOv2 ViT backbone (self-supervised) + linear projection head.

    Attends to object structure rather than background colour, which should
    eliminate the sky-keying weakness observed with MobileNetV3.

    Args:
        variant: ``'dinov2_vits14'`` (384-d) or ``'dinov2_vitb14'`` (768-d).
        embed_dim: Projection head output dimensionality.
        pretrained: Download hub weights on first use (~330 MB, needs internet).
        l2_normalize: L2-normalise the output embedding.

    Note:
        Input normalisation: ImageNet mean/std (same as MobileNetV3).
        Recommended ``image_size``: 224 (= 16 × 14 px patches, aligned).
    """

    def __init__(self, variant: str = "dinov2_vits14", embed_dim: int = 128,
                 pretrained: bool = True, l2_normalize: bool = True) -> None:
        super().__init__()
        self.features = torch.hub.load(
            "facebookresearch/dinov2", variant,
            pretrained=pretrained, verbose=False,
        )
        dino_dim: int = self.features.embed_dim  # 384 (ViT-S) or 768 (ViT-B)
        self.head = nn.Sequential(
            nn.Linear(dino_dim, embed_dim),
            nn.LayerNorm(embed_dim),
        )
        self.embed_dim = embed_dim
        self.l2_normalize = l2_normalize

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Embed a batch of images (CLS token -> projection head)."""
        feats = self.features(x)        # (B, dino_dim)
        x = self.head(feats)
        if self.l2_normalize:
            x = F.normalize(x, p=2, dim=-1)
        return x


# ---------------------------------------------------------------------------
# CLIP visual encoder (Phase 1 — no hardware constraints)
# ---------------------------------------------------------------------------

class CLIPEncoder(nn.Module):
    """OpenCLIP ViT-B/32 visual encoder + linear projection head.

    Args:
        embed_dim: Projection head output dimensionality.
        pretrained: Download OpenAI weights on first use (~350 MB, needs internet).
        l2_normalize: L2-normalise the output embedding.

    Note:
        Input normalisation: CLIP mean/std (see ``BACKBONE_NORM['clip_vit_b32']``).
        Recommended ``image_size``: 224.
        Requires ``open-clip-torch`` (``pip install open-clip-torch``).
    """

    def __init__(self, embed_dim: int = 128, pretrained: bool = True,
                 l2_normalize: bool = True) -> None:
        super().__init__()
        try:
            import open_clip
        except ImportError as exc:
            raise ImportError(
                "open_clip_torch is required for CLIPEncoder. "
                "Install it with:  pip install open-clip-torch"
            ) from exc
        clip_model, _, _ = open_clip.create_model_and_transforms(
            "ViT-B-32", pretrained="openai" if pretrained else None
        )
        self.features = clip_model.visual   # (B, 3, 224, 224) -> (B, 512)
        clip_dim: int = self.features.output_dim  # 512 for ViT-B/32
        self.head = nn.Sequential(
            nn.Linear(clip_dim, embed_dim),
            nn.LayerNorm(embed_dim),
        )
        self.embed_dim = embed_dim
        self.l2_normalize = l2_normalize

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Embed a batch of images via the CLIP visual encoder."""
        feats = self.features(x)        # (B, 512)
        x = self.head(feats)
        if self.l2_normalize:
            x = F.normalize(x, p=2, dim=-1)
        return x


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def build_encoder(
    backbone: str = "mobilenetv3",
    embed_dim: int = 128,
    pretrained: bool = True,
    l2_normalize: bool = True,
) -> nn.Module:
    """Instantiate the requested backbone encoder.

    All returned models expose ``.features`` (backbone) and ``.head``
    (projection) for the two-LR AdamW optimiser in ``trainer.py``.

    Args:
        backbone: One of ``'mobilenetv3'``, ``'dinov2_vits14'``,
            ``'dinov2_vitb14'``, ``'clip_vit_b32'``.
        embed_dim: Projection head output dimensionality.
        pretrained: Load pre-trained weights.
        l2_normalize: L2-normalise the output embedding.
    """
    if backbone == "mobilenetv3":
        return ProtoNetEncoder(embed_dim=embed_dim, pretrained=pretrained,
                               l2_normalize=l2_normalize)
    if backbone in ("dinov2_vits14", "dinov2_vitb14"):
        return DinoV2Encoder(variant=backbone, embed_dim=embed_dim,
                             pretrained=pretrained, l2_normalize=l2_normalize)
    if backbone == "clip_vit_b32":
        return CLIPEncoder(embed_dim=embed_dim, pretrained=pretrained,
                           l2_normalize=l2_normalize)
    raise ValueError(
        f"Unknown backbone {backbone!r}. "
        "Choices: mobilenetv3, dinov2_vits14, dinov2_vitb14, clip_vit_b32"
    )
