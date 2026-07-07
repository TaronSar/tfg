"""Distance metrics for prototypical scoring (Snell et al. 2017)."""
from __future__ import annotations

import torch


def euclidean_logits(
    queries: torch.Tensor, prototypes: torch.Tensor
) -> torch.Tensor:
    """Negative squared Euclidean distance logits (Snell et al. 2017).

    Squared Euclidean is a Bregman divergence, which justifies the class mean as
    the optimal prototype. ``logits = -||q - p||^2`` so that a softmax over them
    yields the prototypical-network posterior. On the unit sphere this is
    rank-equivalent to scaled cosine; the Euclidean form is kept for
    paper-faithfulness and to support an unnormalised ablation.

    Args:
        queries: Query embeddings, shape ``(Q, D)``.
        prototypes: Class prototypes, shape ``(N, D)``.

    Returns:
        Logit matrix of shape ``(Q, N)``.
    """
    dists = torch.cdist(queries, prototypes, p=2) ** 2
    return -dists


def cosine_logits(
    queries: torch.Tensor, prototypes: torch.Tensor, scale: float = 10.0
) -> torch.Tensor:
    """Scaled cosine-similarity logits (kept for the metric ablation).

    Args:
        queries: Query embeddings, shape ``(Q, D)``.
        prototypes: Class prototypes, shape ``(N, D)``.
        scale: Temperature multiplier applied to the cosine similarity.

    Returns:
        Logit matrix of shape ``(Q, N)``.
    """
    return scale * queries @ prototypes.t()
