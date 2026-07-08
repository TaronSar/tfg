"""Prototype construction: mean (Snell et al.) and attention aggregation."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def build_prototypes(
    support: torch.Tensor,
    support_labels: torch.Tensor,
    n_way: int,
    normalize: bool = True,
) -> torch.Tensor:
    """Compute the mean prototype per class (Snell et al. 2017).

    The class mean is optimal under a Bregman divergence such as squared
    Euclidean distance.

    Args:
        support: Support embeddings, shape ``(S, D)``.
        support_labels: Integer class labels in ``[0, n_way)``, shape ``(S,)``.
        n_way: Number of classes in the episode.
        normalize: Re-project each prototype onto the unit sphere (use with
            normalised embeddings; disable for the unnormalised ablation).

    Returns:
        Prototype tensor of shape ``(n_way, D)``.
    """
    protos = torch.zeros(n_way, support.size(1), device=support.device)
    for c in range(n_way):
        protos[c] = support[support_labels == c].mean(dim=0)
    if normalize:
        protos = F.normalize(protos, p=2, dim=-1)
    return protos


def attention_prototype(
    query: torch.Tensor,
    gallery: torch.Tensor,
    tau: float = 0.1,
) -> torch.Tensor:
    """Attention-weighted adaptive prototype for a single query (Approach 2).

    Weights each enrolled view by its similarity to the current query so the
    views closest to the observed viewpoint dominate the prototype.

    Note (Q4): mean aggregation is the deployment default; attention inflates
    impostor scores at ``k >= 5`` and is documented-but-rejected for production.

    Args:
        query: L2-normalised query embedding, shape ``(D,)``.
        gallery: L2-normalised enrolled views, shape ``(V, D)``.
        tau: Softmax temperature over the view-similarity logits.

    Returns:
        L2-normalised adaptive prototype, shape ``(D,)``.
    """
    sims = gallery @ query
    weights = torch.softmax(sims / tau, dim=0)
    proto = (weights.unsqueeze(1) * gallery).sum(dim=0)
    return F.normalize(proto, p=2, dim=0)
