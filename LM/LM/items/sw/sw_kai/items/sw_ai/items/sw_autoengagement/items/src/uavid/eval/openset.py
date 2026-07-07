"""Open-set target-vs-impostor evaluation on held-out identities.

The deployment metric is **cross-domain AUC**: enrollment gallery vs operational
(val) queries. The scoring logic here is MLflow-free; the CLI wrapper lives in
``scripts/evaluate.py``.
"""
from __future__ import annotations

import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from src.uavid.dataset import IdentityIndex, load_image
from src.uavid.model import attention_prototype


@torch.no_grad()
def embed_paths(model, paths, tfm, device, batch_size: int = 64) -> torch.Tensor:
    """Embed a list of image paths in batches and return the stacked tensor."""
    out = []
    for i in range(0, len(paths), batch_size):
        batch = torch.stack([load_image(p, tfm) for p in paths[i:i + batch_size]])
        out.append(model(batch.to(device)))
    return torch.cat(out, dim=0)


def roc_auc(genuine: np.ndarray, impostor: np.ndarray) -> float:
    """Compute ROC-AUC via the rank statistic (no sklearn dependency).

    Args:
        genuine: Genuine (target) match scores.
        impostor: Impostor match scores.

    Returns:
        Area under the ROC curve in ``[0, 1]``.
    """
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones_like(genuine), np.zeros_like(impostor)])
    order = scores.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    n_pos, n_neg = len(genuine), len(impostor)
    return (ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def tpr_at_fpr(genuine: np.ndarray, impostor: np.ndarray, fpr: float) -> tuple[float, float]:
    """Return ``(TPR, threshold)`` at a fixed false-positive rate ``fpr``."""
    thr = np.quantile(impostor, 1 - fpr)
    return float((genuine >= thr).mean()), float(thr)


def evaluate_openset(
    model,
    query_index: IdentityIndex,
    gallery_index: IdentityIndex,
    tfm,
    device: str,
    *,
    k_shot: int = 5,
    max_queries_per_id: int = 30,
    agg: str = "mean",
    tau: float = 0.1,
    metric: str = "euclidean",
    normalize: bool = True,
    seed: int = 42,
) -> dict:
    """Run open-set target-vs-impostor evaluation and return a metrics dict.

    Args:
        model: Encoder in eval mode on ``device``.
        query_index: Identity index for query images.
        gallery_index: Identity index for gallery (enrollment) images. Pass the
            same object as ``query_index`` for same-domain evaluation.
        tfm: Eval transform.
        device: Torch device string.
        k_shot: Number of enrollment views per identity.
        max_queries_per_id: Cap on genuine queries scored per identity.
        agg: ``"mean"`` (deployment default) or ``"attention"``.
        tau: Attention temperature (when ``agg == "attention"``).
        metric: ``"euclidean"`` or ``"cosine"``.
        normalize: Whether embeddings are L2-normalised.
        seed: RNG seed for deterministic sampling.

    Returns:
        Dict with ``roc_auc``, ``genuine_mean``, ``impostor_mean`` and
        ``tpr_at_fpr`` (a dict keyed by FPR).
    """
    random.seed(seed)
    same_split = gallery_index is query_index

    query_pools = {n: random.sample(list(query_index.identities[n]),
                                    len(query_index.identities[n]))
                   for n in query_index.names}
    gallery_pools = {n: random.sample(list(gallery_index.identities[n]),
                                      len(gallery_index.identities[n]))
                     for n in gallery_index.names}

    genuine_all: list[float] = []
    impostor_all: list[float] = []
    for name in query_index.names:
        query_paths_all = query_pools[name]
        gallery_paths_all = gallery_pools.get(name)
        if not gallery_paths_all:
            continue
        if same_split:
            if len(query_paths_all) <= k_shot:
                continue
            enroll_paths = query_paths_all[:k_shot]
            query_paths = query_paths_all[k_shot:k_shot + max_queries_per_id]
        else:
            enroll_paths = (random.sample(gallery_paths_all, k_shot)
                            if len(gallery_paths_all) >= k_shot
                            else random.choices(gallery_paths_all, k=k_shot))
            query_paths = query_paths_all[:max_queries_per_id]
            if not query_paths:
                continue

        gallery = embed_paths(model, enroll_paths, tfm, device)
        if normalize:
            gallery = F.normalize(gallery, p=2, dim=-1)
            mean_proto = F.normalize(gallery.mean(dim=0), p=2, dim=0)
        else:
            mean_proto = gallery.mean(dim=0)

        def score(q_emb, _gallery=gallery, _mean_proto=mean_proto):
            out = []
            for q in q_emb:
                if agg == "attention" and normalize:
                    proto = attention_prototype(q, _gallery, tau=tau)
                else:
                    proto = _mean_proto
                if metric == "cosine" or normalize:
                    out.append(float(q @ proto))
                else:
                    out.append(-float(((q - proto) ** 2).sum()))
            return out

        genuine_all += score(embed_paths(model, query_paths, tfm, device))

        imp_paths: list[Path] = []
        for other in query_index.names:
            if other == name:
                continue
            imp_paths += random.sample(query_pools[other],
                                       min(3, len(query_pools[other])))
        impostor_all += score(embed_paths(model, imp_paths, tfm, device))

    g, i = np.array(genuine_all), np.array(impostor_all)
    if len(g) == 0 or len(i) == 0:
        raise RuntimeError("No genuine/impostor scores produced. Check split/gallery overlap.")

    results = {
        "k_shot": k_shot,
        "agg": agg,
        "roc_auc": roc_auc(g, i),
        "genuine_n": int(len(g)),
        "genuine_mean": float(g.mean()),
        "impostor_n": int(len(i)),
        "impostor_mean": float(i.mean()),
        "tpr_at_fpr": {},
    }
    for fpr in (0.01, 0.05, 0.10):
        tpr, thr = tpr_at_fpr(g, i, fpr)
        results["tpr_at_fpr"][f"{fpr:.2f}"] = {"tpr": tpr, "threshold": thr}
    return results
