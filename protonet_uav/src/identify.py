"""Identify: compare query image(s) against an enrolled gallery.

Usage:
    python -m src.identify --checkpoint checkpoints/best.pth \
        --gallery gallery.npy --images path/to/queries/ \
        --agg attention --threshold 0.6

Aggregation:
    mean      -> static prototype = normalized mean of enrolled views (baseline)
    attention -> Approach 2: per-query attention-weighted adaptive prototype
"""

import argparse
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

from src.dataset import IMG_EXTS, build_transform, load_image
from src.model import ProtoNetEncoder, attention_prototype


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument("--gallery", required=True)
    ap.add_argument("--images", required=True, help="Query image or folder")
    ap.add_argument("--agg", choices=["mean", "attention"], default="mean")
    ap.add_argument("--tau", type=float, default=0.1, help="Attention temperature")
    ap.add_argument("--threshold", type=float, default=0.6,
                    help="Cosine similarity above which the target is declared MATCH")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    embed_dim, image_size = 128, 224
    metric, normalize = "euclidean", True
    model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=True, l2_normalize=normalize)
    if args.checkpoint:
        ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
        embed_dim = ckpt.get("embed_dim", 128)
        image_size = ckpt.get("image_size", 224)
        metric = ckpt.get("metric", "euclidean")
        normalize = ckpt.get("l2_normalize", True)
        model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False,
                                l2_normalize=normalize)
        model.load_state_dict(ckpt["model"])
    model.eval().to(device)

    gallery = torch.from_numpy(np.load(args.gallery)).float().to(device)  # (V, D)
    if normalize:
        gallery = F.normalize(gallery, p=2, dim=-1)
        mean_proto = F.normalize(gallery.mean(dim=0), p=2, dim=0)
    else:
        mean_proto = gallery.mean(dim=0)

    src = Path(args.images)
    paths = ([src] if src.is_file()
             else sorted(f for f in src.rglob("*") if f.suffix.lower() in IMG_EXTS))
    if not paths:
        raise SystemExit(f"No images found in {src}")

    tfm = build_transform(image_size, train=False)
    batch = torch.stack([load_image(p, tfm) for p in paths]).to(device)
    q_emb = model(batch)  # (Q, D)

    use_cosine_score = (metric == "cosine") or normalize
    score_name = "cos" if use_cosine_score else "-d^2"
    print(f"metric={metric} normalize={normalize}  (score={score_name}, higher=better)")
    print(f"{'image':<50} {'score':>8}  verdict")
    scores = []
    for path, q in zip(paths, q_emb):
        if args.agg == "attention" and normalize:
            proto = attention_prototype(q, gallery, tau=args.tau)
        else:
            proto = mean_proto
        if use_cosine_score:
            score = float(q @ proto)
        else:
            score = -float(((q - proto) ** 2).sum())
        scores.append(score)
        verdict = "MATCH" if score >= args.threshold else "unknown"
        print(f"{str(path)[-50:]:<50} {score:>8.4f}  {verdict}")

    s = np.array(scores)
    print(f"\nqueries: {len(s)} | mean {s.mean():.4f} | min {s.min():.4f} | "
          f"max {s.max():.4f} | matches @ {args.threshold}: {(s >= args.threshold).sum()}")


if __name__ == "__main__":
    main()
