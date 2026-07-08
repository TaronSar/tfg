import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.uavid.common.constants import IMG_EXTS
from src.uavid.common.transforms import build_transform
from src.uavid.dataset import load_image
from src.uavid.model import BACKBONE_NORM, attention_prototype, build_encoder


@torch.no_grad()
def embed_paths(model, paths, transform, device):
    batch = torch.stack([load_image(path, transform) for path in paths]).to(device)
    return model(batch)


def image_paths(path):
    root = Path(path)
    if root.is_file():
        return [root] if root.suffix.lower() in IMG_EXTS else []
    return sorted(path for path in root.rglob("*") if path.suffix.lower() in IMG_EXTS)


def load_model(checkpoint, device):
    ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
    embed_dim = ckpt.get("embed_dim", 128)
    image_size = ckpt.get("image_size", 224)
    normalize = ckpt.get("l2_normalize", True)
    backbone = ckpt.get("backbone", "mobilenetv3")
    model = build_encoder(backbone, embed_dim=embed_dim, pretrained=False, l2_normalize=normalize)
    model.load_state_dict(ckpt["model"])
    model.eval().to(device)
    norm_mean, norm_std = BACKBONE_NORM[backbone]
    return model, image_size, normalize, ckpt, norm_mean, norm_std


def score_queries(query_embeddings, gallery, normalize, agg, tau):
    if normalize:
        gallery = F.normalize(gallery, p=2, dim=-1)
        mean_proto = F.normalize(gallery.mean(dim=0), p=2, dim=0)
    else:
        mean_proto = gallery.mean(dim=0)

    scores = []
    for query in query_embeddings:
        if agg == "attention" and normalize:
            proto = attention_prototype(query, gallery, tau=tau)
        else:
            proto = mean_proto
        if normalize:
            score = float(query @ proto)
        else:
            score = -float(((query - proto) ** 2).sum())
        scores.append(score)
    return np.array(scores, dtype=np.float32)


def folder_score(scores, rule, top_k):
    if rule == "max":
        return float(scores.max())
    if rule == "mean":
        return float(scores.mean())
    k = min(top_k, len(scores))
    return float(np.sort(scores)[-k:].mean())


@torch.no_grad()
def main():
    parser = argparse.ArgumentParser(description="Run the close-enrollment vs far-query UAV demo.")
    parser.add_argument("--checkpoint", required=True)
    parser.add_argument(
        "--enrollment", required=True, help="Folder with close client UAV reference images."
    )
    parser.add_argument(
        "--queries", required=True, help="Folder containing one subfolder per candidate sighting."
    )
    parser.add_argument("--gallery_out", default="data/demo/client_uav/gallery.npy")
    parser.add_argument("--agg", choices=["mean", "attention"], default="mean")
    parser.add_argument("--tau", type=float, default=0.1)
    parser.add_argument("--folder_rule", choices=["topk_mean", "max", "mean"], default="topk_mean")
    parser.add_argument("--top_k", type=int, default=2)
    parser.add_argument("--threshold", type=float, default=0.4)
    parser.add_argument("--csv_out", default="csvs/demo_real_world_scores.csv")
    parser.add_argument("--show_images", action="store_true")
    args = parser.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model, image_size, normalize, ckpt, norm_mean, norm_std = load_model(args.checkpoint, device)
    transform = build_transform(image_size, train=False, mean=norm_mean, std=norm_std)

    enrollment_paths = image_paths(args.enrollment)
    if not enrollment_paths:
        raise SystemExit(f"No enrollment images found in {args.enrollment}")

    gallery = embed_paths(model, enrollment_paths, transform, device)
    np.save(args.gallery_out, gallery.cpu().numpy().astype(np.float32))

    query_root = Path(args.queries)
    candidate_dirs = sorted(path for path in query_root.iterdir() if path.is_dir())
    if not candidate_dirs:
        candidate_dirs = [query_root]

    rows = []
    print(f"Loaded {args.checkpoint} (epoch {ckpt.get('epoch')}, val_acc {ckpt.get('val_acc')})")
    print(f"Enrolled {len(enrollment_paths)} close images -> {args.gallery_out}")
    print(f"Decision: {args.folder_rule} threshold={args.threshold} agg={args.agg}\n")
    print(f"{'candidate':<24} {'n':>3} {'mean':>8} {'max':>8} {'topk':>8} {'decision':>10}")

    best_name = None
    best_score = -float("inf")
    for candidate_dir in candidate_dirs:
        paths = image_paths(candidate_dir)
        if not paths:
            continue
        query_embeddings = embed_paths(model, paths, transform, device)
        scores = score_queries(query_embeddings, gallery, normalize, args.agg, args.tau)
        decision_score = folder_score(scores, args.folder_rule, args.top_k)
        topk = folder_score(scores, "topk_mean", args.top_k)
        decision = "MATCH" if decision_score >= args.threshold else "unknown"
        if decision_score > best_score:
            best_name = candidate_dir.name
            best_score = decision_score
        print(
            f"{candidate_dir.name:<24} {len(paths):>3} {scores.mean():>8.4f} "
            f"{scores.max():>8.4f} {topk:>8.4f} {decision:>10}"
        )
        for path, score in zip(paths, scores, strict=False):
            rows.append(
                {
                    "candidate": candidate_dir.name,
                    "image": str(path),
                    "score": float(score),
                    "folder_score": decision_score,
                    "decision": decision,
                }
            )
        if args.show_images:
            for path, score in zip(paths, scores, strict=False):
                print(f"  {path.name:<48} {score:>8.4f}")

    csv_path = Path(args.csv_out)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=["candidate", "image", "score", "folder_score", "decision"]
        )
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nBest candidate: {best_name} ({best_score:.4f})")
    print(f"Saved per-image scores -> {csv_path}")


if __name__ == "__main__":
    main()
