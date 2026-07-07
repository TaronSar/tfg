"""Open-set evaluation on held-out identities — the test that matters.

For each query identity: enroll K random gallery views, then score
    - genuine queries  (images of that identity from the query split)
    - impostor queries (images of all other query identities)
Reports ROC-AUC, best-F1 threshold, and TPR at fixed FPRs.

Usage:
    python -m src.eval_openset --checkpoint checkpoints/best.pth \
        --data_root ./data --k_shot 5 --agg attention
    python -m src.eval_openset --checkpoint checkpoints/best.pth \
        --data_root ./data --gallery_split enrollment --split val --k_shot 5
"""

import argparse
import random
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from src.dataset import IdentityIndex, build_transform, load_image
from src.model import ProtoNetEncoder, attention_prototype, build_encoder, BACKBONE_NORM


@torch.no_grad()
def embed_paths(model, paths, tfm, device, batch_size=64):
    out = []
    for i in range(0, len(paths), batch_size):
        batch = torch.stack([load_image(p, tfm) for p in paths[i:i + batch_size]])
        out.append(model(batch.to(device)))
    return torch.cat(out, dim=0)


def roc_auc(genuine: np.ndarray, impostor: np.ndarray) -> float:
    """AUC via rank statistic (no sklearn dependency)."""
    scores = np.concatenate([genuine, impostor])
    labels = np.concatenate([np.ones_like(genuine), np.zeros_like(impostor)])
    order = scores.argsort()
    ranks = np.empty_like(order, dtype=float)
    ranks[order] = np.arange(1, len(scores) + 1)
    n_pos, n_neg = len(genuine), len(impostor)
    return (ranks[labels == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)


def tpr_at_fpr(genuine: np.ndarray, impostor: np.ndarray, fpr: float):
    thr = np.quantile(impostor, 1 - fpr)
    return (genuine >= thr).mean(), thr


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--data_root", required=True)
    ap.add_argument("--split", default="val")
    ap.add_argument("--gallery_split", default=None,
                    help="Split used for enrollment/gallery images. Default: same as --split.")
    ap.add_argument("--k_shot", type=int, default=5)
    ap.add_argument("--max_queries_per_id", type=int, default=30)
    ap.add_argument("--agg", choices=["mean", "attention"], default="mean")
    ap.add_argument("--tau", type=float, default=0.1)
    ap.add_argument("--seed", type=int, default=42)
    args = ap.parse_args()

    random.seed(args.seed)
    device = "cuda" if torch.cuda.is_available() else "cpu"

    embed_dim, image_size = 128, 224
    metric, normalize = "euclidean", True
    backbone = "mobilenetv3"
    model = build_encoder(backbone, embed_dim=embed_dim, pretrained=True,
                          l2_normalize=normalize)
    if args.checkpoint:
        ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
        embed_dim = ckpt.get("embed_dim", 128)
        image_size = ckpt.get("image_size", 224)
        metric = ckpt.get("metric", "euclidean")
        normalize = ckpt.get("l2_normalize", True)
        backbone = ckpt.get("backbone", "mobilenetv3")
        model = build_encoder(backbone, embed_dim=embed_dim, pretrained=False,
                              l2_normalize=normalize)
        model.load_state_dict(ckpt["model"])
        print(f"Loaded {args.checkpoint} | backbone={backbone} metric={metric} normalize={normalize}")
    else:
        print("Zero-shot ImageNet features (no checkpoint)")
    model.eval().to(device)

    query_index = IdentityIndex(Path(args.data_root) / args.split)
    gallery_split = args.gallery_split or args.split
    gallery_index = query_index if gallery_split == args.split else IdentityIndex(Path(args.data_root) / gallery_split)
    print(f"query {args.split}: {query_index.stats()}")
    if gallery_index is query_index:
        print(f"gallery {gallery_split}: same split as query")
    else:
        print(f"gallery {gallery_split}: {gallery_index.stats()}")
    print()
    norm_mean, norm_std = BACKBONE_NORM[backbone]
    tfm = build_transform(image_size, train=False, mean=norm_mean, std=norm_std)

    # Pre-shuffle pools per identity so repeated scoring is deterministic for a seed.
    query_pools = {}
    for name in query_index.names:
        paths = query_index.identities[name]
        random.shuffle(paths := list(paths))
        query_pools[name] = paths

    gallery_pools = {}
    for name in gallery_index.names:
        paths = gallery_index.identities[name]
        random.shuffle(paths := list(paths))
        gallery_pools[name] = paths

    genuine_all, impostor_all = [], []
    skipped_missing_gallery = []
    skipped_no_queries = []
    for name in query_index.names:
        query_paths_all = query_pools[name]
        gallery_paths_all = gallery_pools.get(name)
        if not gallery_paths_all:
            skipped_missing_gallery.append(name)
            continue
        if gallery_index is query_index:
            if len(query_paths_all) <= args.k_shot:
                skipped_no_queries.append(name)
                continue
            enroll_paths = query_paths_all[: args.k_shot]
            query_paths = query_paths_all[args.k_shot: args.k_shot + args.max_queries_per_id]
        else:
            enroll_paths = (random.sample(gallery_paths_all, args.k_shot)
                            if len(gallery_paths_all) >= args.k_shot
                            else random.choices(gallery_paths_all, k=args.k_shot))
            query_paths = query_paths_all[: args.max_queries_per_id]
            if not query_paths:
                skipped_no_queries.append(name)
                continue

        gallery = embed_paths(model, enroll_paths, tfm, device)
        if normalize:
            gallery = F.normalize(gallery, p=2, dim=-1)
            mean_proto = F.normalize(gallery.mean(dim=0), p=2, dim=0)
        else:
            mean_proto = gallery.mean(dim=0)

        def score(q_emb):
            out = []
            for q in q_emb:
                if args.agg == "attention" and normalize:
                    proto = attention_prototype(q, gallery, tau=args.tau)
                else:
                    proto = mean_proto
                if metric == "cosine" or normalize:
                    # on the unit sphere these are rank-equivalent; cosine is bounded [-1,1]
                    out.append(float(q @ proto))
                else:
                    out.append(-float(((q - proto) ** 2).sum()))  # neg sq Euclidean
            return out

        genuine_all += score(embed_paths(model, query_paths, tfm, device))

        imp_paths = []
        for other in query_index.names:
            if other == name:
                continue
            imp_paths += random.sample(
                query_pools[other], min(3, len(query_pools[other])))
        impostor_all += score(embed_paths(model, imp_paths, tfm, device))

    g, i = np.array(genuine_all), np.array(impostor_all)
    if len(g) == 0 or len(i) == 0:
        raise RuntimeError("No genuine/impostor scores were produced. Check split/gallery identity overlap.")
    auc = roc_auc(g, i)
    print(f"k_shot={args.k_shot} agg={args.agg}")
    print(f"query_split={args.split} gallery_split={gallery_split}")
    if skipped_missing_gallery:
        print(f"skipped missing gallery identities: {len(skipped_missing_gallery)}")
    if skipped_no_queries:
        print(f"skipped identities without query images: {len(skipped_no_queries)}")
    print(f"genuine:  n={len(g)} mean={g.mean():.4f}")
    print(f"impostor: n={len(i)} mean={i.mean():.4f}")
    print(f"ROC-AUC:  {auc:.4f}")
    for fpr in (0.01, 0.05, 0.10):
        tpr, thr = tpr_at_fpr(g, i, fpr)
        print(f"TPR @ FPR={fpr:.0%}: {tpr:.3f}  (threshold {thr:.4f})")


if __name__ == "__main__":
    main()
