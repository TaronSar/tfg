"""Encoder for few-shot UAV identification.

Supported backbones (--backbone in train.py):
  mobilenetv3   MobileNetV3-Small + projection head (original TFG config)
  dinov2_vits14 DINOv2 ViT-S/14 (384-d) + projection head
  dinov2_vitb14 DINOv2 ViT-B/14 (768-d) + projection head
  clip_vit_b32  OpenAI CLIP ViT-B/32 (512-d visual) + projection head

All encoders expose .features (backbone) and .head (projection) for the
two-LR AdamW optimizer in train.py.  Use build_encoder() as the factory.
BACKBONE_NORM maps backbone name -> (mean, std) for build_transform().
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision

# Per-backbone input normalisation constants.
# Keep in sync with src/dataset.py IMAGENET_MEAN/STD and CLIP_MEAN/STD.
BACKBONE_NORM: dict[str, tuple[list[float], list[float]]] = {
    "mobilenetv3":  ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    "dinov2_vits14": ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    "dinov2_vitb14": ([0.485, 0.456, 0.406], [0.229, 0.224, 0.225]),
    "clip_vit_b32": ([0.48145466, 0.4578275, 0.40821073],
                     [0.26862954, 0.26130258, 0.27577711]),
}


class ProtoNetEncoder(nn.Module):
    def __init__(self, embed_dim: int = 128, pretrained: bool = True,
                 l2_normalize: bool = True):
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
        x = self.features(x)
        x = self.avgpool(x)
        x = self.head(x)
        if self.l2_normalize:
            x = F.normalize(x, p=2, dim=-1)
        return x


def euclidean_logits(
    queries: torch.Tensor, prototypes: torch.Tensor
) -> torch.Tensor:
    """Negative squared Euclidean distance (Snell et al. 2017).

    Squared Euclidean is a Bregman divergence, which is what justifies the
    class mean as the optimal prototype. Logits = -||q - p||^2 so that
    softmax over them yields the prototypical-network posterior.

    Note: when embeddings are L2-normalized, ||q-p||^2 = 2 - 2 cos(q,p), so
    this is rank-equivalent to scaled cosine on the unit sphere. Kept as
    Euclidean for paper-faithfulness and to support an unnormalized ablation.

    queries:    (Q, D)
    prototypes: (N, D)
    returns:    (Q, N) logits
    """
    # (Q, N) pairwise squared distances
    dists = torch.cdist(queries, prototypes, p=2) ** 2
    return -dists


def cosine_logits(
    queries: torch.Tensor, prototypes: torch.Tensor, scale: float = 10.0
) -> torch.Tensor:
    """Scaled cosine similarity (kept for the metric ablation)."""
    return scale * queries @ prototypes.t()


def build_prototypes(
    support: torch.Tensor, support_labels: torch.Tensor, n_way: int,
    normalize: bool = True
) -> torch.Tensor:
    """Mean prototype per class (Snell et al.: the class mean is optimal
    under a Bregman divergence such as squared Euclidean).

    support: (S, D) embeddings
    support_labels: (S,) ints in [0, n_way)
    normalize: re-project the mean onto the unit sphere (use with normalized
               embeddings; disable for the unnormalized-Euclidean ablation).
    returns: (n_way, D)
    """
    protos = torch.zeros(n_way, support.size(1), device=support.device)
    for c in range(n_way):
        protos[c] = support[support_labels == c].mean(dim=0)
    if normalize:
        protos = F.normalize(protos, p=2, dim=-1)
    return protos


def attention_prototype(
    query: torch.Tensor, gallery: torch.Tensor, tau: float = 0.1
) -> torch.Tensor:
    """Approach 2: attention-weighted adaptive prototype for a single query.

    Weights each enrolled view by its similarity to the current query, so the
    views closest to the observed viewpoint dominate the prototype.

    query:   (D,)   L2-normalized
    gallery: (V, D) L2-normalized enrolled views
    returns: (D,)   L2-normalized adaptive prototype
    """
    sims = gallery @ query              # (V,)
    weights = torch.softmax(sims / tau, dim=0)
    proto = (weights.unsqueeze(1) * gallery).sum(dim=0)
    return F.normalize(proto, p=2, dim=0)


# ---------------------------------------------------------------------------
# DINOv2 encoder (Phase 1 — no hardware constraints)
# ---------------------------------------------------------------------------

class DinoV2Encoder(nn.Module):
    """DINOv2 ViT backbone (self-supervised) + linear projection head.

    Attends to object structure rather than background colour, which should
    eliminate the sky-keying weakness observed with MobileNetV3.

    variant: 'dinov2_vits14' (384-d, lighter) or 'dinov2_vitb14' (768-d).
    Weights are downloaded from facebookresearch/dinov2 on first use (~330 MB
    for ViT-S, ~330 MB for ViT-B).  Requires internet access on first run.

    Input normalisation: ImageNet mean/std (same as MobileNetV3).
    Recommended image_size: 224 (= 16 × 14 px patches, aligned).
    """

    def __init__(self, variant: str = "dinov2_vits14", embed_dim: int = 128,
                 pretrained: bool = True, l2_normalize: bool = True):
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
        feats = self.features(x)        # CLS token: (B, dino_dim)
        x = self.head(feats)
        if self.l2_normalize:
            x = F.normalize(x, p=2, dim=-1)
        return x


# ---------------------------------------------------------------------------
# CLIP visual encoder (Phase 1 — no hardware constraints)
# ---------------------------------------------------------------------------

class CLIPEncoder(nn.Module):
    """OpenCLIP ViT-B/32 visual encoder + linear projection head.

    CLIP visual features are language-aligned and object-centric by training,
    which may help on sparse UAV silhouettes.

    Requires: pip install open-clip-torch
    Weights (~350 MB) downloaded from OpenAI on first use.

    Input normalisation: CLIP mean/std (see BACKBONE_NORM['clip_vit_b32']).
    Recommended image_size: 224.
    """

    def __init__(self, embed_dim: int = 128, pretrained: bool = True,
                 l2_normalize: bool = True):
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

    All returned models expose .features (backbone) and .head (projection)
    for the two-LR AdamW optimiser in train.py.
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
