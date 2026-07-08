"""plot_embedding_map.py — 2D map of image embeddings, colored by identity.

Each node = one image. Each color = one identity. Lets you SEE whether the
frozen ProtoNet encoder pulls same-identity images together and pushes
different identities apart — the property the whole verification system relies
on.

Identities can be given two ways (you can mix both):

  --data_root FOLDER
        Every immediate subfolder of FOLDER is treated as one identity.

  --identity NAME=PATH  (repeatable)
        Explicit identity name -> image folder (or single image).

Projection:
  --method tsne (default) | pca
  t-SNE shows local cluster structure; PCA is a faithful linear projection.
  Falls back to PCA automatically if there are too few images for t-SNE.

Usage:
    python scripts/plot_embedding_map.py \
        --checkpoint checkpoints_yolox_crops_mixed_domain/best.pth \
        --identity target=data/demo/camera_video_fragmentation_preview \
        --identity impostor=data/demo/video_demo_enrollment/impostor \
        --identity vector_uav=data/demo/video_vector_uav_cropped \
        --out graphs/embedding_map.png
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from src.model import ProtoNetEncoder  # noqa: E402

from src.uavid.common.constants import IMG_EXTS  # noqa: E402
from src.uavid.common.transforms import build_transform  # noqa: E402
from src.uavid.dataset import load_image  # noqa: E402


def load_model(checkpoint):
    device = "cuda" if torch.cuda.is_available() else "cpu"
    embed_dim, image_size, normalize = 128, 224, True
    model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=True, l2_normalize=normalize)
    if checkpoint:
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
        embed_dim = ckpt.get("embed_dim", 128)
        image_size = ckpt.get("image_size", 224)
        normalize = ckpt.get("l2_normalize", True)
        model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False, l2_normalize=normalize)
        model.load_state_dict(ckpt["model"])
        print(f"Loaded {checkpoint} (epoch {ckpt.get('epoch')}, val_acc {ckpt.get('val_acc')})")
    else:
        print("No checkpoint -> zero-shot ImageNet features")
    model.eval().to(device)
    return model, image_size, device


def images_in(path: Path) -> list[Path]:
    if path.is_file() and path.suffix.lower() in IMG_EXTS:
        return [path]
    return sorted(f for f in path.rglob("*") if f.suffix.lower() in IMG_EXTS)


@torch.no_grad()
def embed(model, tfm, paths, device, batch=64) -> np.ndarray:
    out = []
    for i in range(0, len(paths), batch):
        chunk = paths[i : i + batch]
        x = torch.stack([load_image(p, tfm) for p in chunk]).to(device)
        out.append(model(x).cpu().numpy())
    return np.concatenate(out, axis=0).astype(np.float32)


def collect_identities(args) -> dict[str, list[Path]]:
    identities: dict[str, list[Path]] = {}
    for root_spec in args.data_root or []:
        root = Path(root_spec)
        # Prefix with the root's folder name (e.g. train/val) so identities with
        # the same name in different splits stay distinct.
        prefix = f"{root.name}/" if (args.data_root and len(args.data_root) > 1) else ""
        for sub in sorted(p for p in root.iterdir() if p.is_dir()):
            imgs = images_in(sub)
            if imgs:
                identities[f"{prefix}{sub.name}"] = imgs
    for spec in args.identity or []:
        if "=" not in spec:
            raise SystemExit(f"--identity must be NAME=PATH, got {spec!r}")
        name, path = spec.split("=", 1)
        imgs = images_in(Path(path))
        if not imgs:
            print(f"  [warn] no images for identity {name!r} at {path}")
            continue
        identities[name] = imgs
    if not identities:
        raise SystemExit("No identities collected. Use --data_root and/or --identity.")
    return identities


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None)
    ap.add_argument(
        "--data_root", action="append", help="Folder whose subfolders are identities (repeatable)."
    )
    ap.add_argument("--identity", action="append", help="NAME=PATH for one identity (repeatable).")
    ap.add_argument(
        "--method",
        choices=["tsne", "pca", "tsne3d", "pca3d", "simmatrix"],
        default="tsne",
        help="2d: tsne/pca | 3d: tsne3d/pca3d | simmatrix: full-128D "
        "pairwise cosine heatmap (no dimensionality reduction).",
    )
    ap.add_argument(
        "--max_per_identity", type=int, default=0, help="Cap images per identity (0 = all)."
    )
    ap.add_argument(
        "--perplexity", type=float, default=30.0, help="t-SNE perplexity (auto-clamped to N)."
    )
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="graphs/embedding_map.png")
    args = ap.parse_args()

    identities = collect_identities(args)
    if args.max_per_identity > 0:
        identities = {k: v[: args.max_per_identity] for k, v in identities.items()}

    model, image_size, device = load_model(args.checkpoint)
    tfm = build_transform(image_size, train=False)

    all_paths, labels, names = [], [], list(identities.keys())
    for idx, name in enumerate(names):
        for p in identities[name]:
            all_paths.append(p)
            labels.append(idx)
    labels = np.array(labels)
    print(f"Embedding {len(all_paths)} images across {len(names)} identities...")
    emb = embed(model, tfm, all_paths, device)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    n = len(all_paths)

    # ── Full-128D pairwise cosine heatmap (no reduction) ─────────────────────
    if args.method == "simmatrix":
        order = np.argsort(labels, kind="stable")
        e = emb[order]
        e = e / (np.linalg.norm(e, axis=1, keepdims=True) + 1e-9)
        sim = e @ e.T  # cosine similarity in full 128-D
        lab = labels[order]

        plt.figure(figsize=(10, 9))
        plt.imshow(sim, cmap="viridis", vmin=-1, vmax=1, interpolation="nearest")
        plt.colorbar(label="cosine similarity (computed in full 128-D)")
        # Identity block boundaries + centered tick labels.
        bounds, ticks, tlabels = [], [], []
        start = 0
        for idx in range(len(names)):
            cnt = int((lab == idx).sum())
            if cnt == 0:
                continue
            ticks.append(start + cnt / 2)
            tlabels.append(f"{names[idx]} ({cnt})")
            start += cnt
            bounds.append(start)
        for b in bounds[:-1]:
            plt.axhline(b - 0.5, color="white", linewidth=0.5)
            plt.axvline(b - 0.5, color="white", linewidth=0.5)
        fs = 7 if len(names) > 20 else 9
        plt.xticks(ticks, tlabels, rotation=90, fontsize=fs)
        plt.yticks(ticks, tlabels, fontsize=fs)
        plt.title(
            f"Full 128-D pairwise cosine similarity  |  {len(names)} identities, "
            f"{n} images\nbright blocks on diagonal = same identity clusters "
            f"tightly  |  checkpoint: "
            f"{Path(args.checkpoint).name if args.checkpoint else 'imagenet'}"
        )
        plt.tight_layout()
        plt.savefig(out, dpi=150, bbox_inches="tight")
        print(f"Saved -> {out}  (full-128D similarity matrix, {n}x{n})")
        return

    method = args.method
    n_comp = 3 if method.endswith("3d") else 2
    base = method.replace("3d", "")
    if base == "tsne" and n < 5:
        print("Too few points for t-SNE -> using PCA")
        base = "pca"

    if base == "tsne":
        from sklearn.manifold import TSNE

        perp = max(2.0, min(args.perplexity, (n - 1) / 3.0))
        proj = TSNE(
            n_components=n_comp, perplexity=perp, init="pca", random_state=args.seed
        ).fit_transform(emb)
        title = f"t-SNE ({n_comp}D) of image embeddings (perplexity={perp:.0f})"
    else:
        from sklearn.decomposition import PCA

        pca = PCA(n_components=n_comp, random_state=args.seed)
        proj = pca.fit_transform(emb)
        var = pca.explained_variance_ratio_.sum() * 100
        title = f"PCA ({n_comp}D) of image embeddings ({var:.1f}% variance shown)"

    # Distinct colors + cycling marker shapes so many identities stay readable.
    n_id = len(names)
    if n_id <= 10:
        colors = [plt.get_cmap("tab10")(i) for i in range(n_id)]
    elif n_id <= 20:
        colors = [plt.get_cmap("tab20")(i) for i in range(n_id)]
    else:
        colors = [plt.get_cmap("gist_ncar")(i / max(1, n_id - 1)) for i in range(n_id)]
    markers = ["o", "s", "^", "D", "v", "P", "X", "*", "<", ">", "p", "h"]

    fig_w = 13 if n_id > 20 else 11
    fig = plt.figure(figsize=(fig_w, 8))
    if n_comp == 3:
        ax = fig.add_subplot(111, projection="3d")
        for idx, name in enumerate(names):
            m = labels == idx
            ax.scatter(
                proj[m, 0],
                proj[m, 1],
                proj[m, 2],
                s=40,
                alpha=0.85,
                color=colors[idx],
                marker=markers[idx % len(markers)],
                edgecolors="black",
                linewidths=0.3,
                label=f"{name} ({m.sum()})",
            )
        ax.set_xlabel("dim 1")
        ax.set_ylabel("dim 2")
        ax.set_zlabel("dim 3")
    else:
        ax = fig.add_subplot(111)
        for idx, name in enumerate(names):
            m = labels == idx
            ax.scatter(
                proj[m, 0],
                proj[m, 1],
                s=46,
                alpha=0.85,
                color=colors[idx],
                marker=markers[idx % len(markers)],
                edgecolors="black",
                linewidths=0.3,
                label=f"{name} ({m.sum()})",
            )
        ax.set_xlabel("dim 1")
        ax.set_ylabel("dim 2")
    ax.set_title(
        title + f"  |  {n_id} identities  |  checkpoint: "
        f"{Path(args.checkpoint).name if args.checkpoint else 'imagenet'}"
    )
    ncol = 2 if n_id > 26 else 1
    ax.legend(
        title="identity (n images)",
        bbox_to_anchor=(1.02, 1),
        loc="upper left",
        borderaxespad=0,
        fontsize=7 if n_id > 20 else 9,
        ncol=ncol,
    )
    plt.tight_layout()

    plt.savefig(out, dpi=150, bbox_inches="tight")
    print(f"Saved -> {out}  ({len(names)} identities, {n} nodes)")


if __name__ == "__main__":
    main()
