"""Enroll a target: embed N reference images -> gallery.npy

This is the client-side step of Option A: only the resulting gallery.npy
would ever leave the client's machine.

Usage:
    python -m src.enroll --checkpoint checkpoints/best.pth \
        --images path/to/target_photos/ --out gallery.npy
"""

import argparse
from pathlib import Path

import numpy as np
import torch

from src.dataset import IMG_EXTS, build_transform, load_image
from src.model import ProtoNetEncoder


@torch.no_grad()
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", default=None,
                    help="Trained checkpoint. Omit to use the ImageNet-pretrained encoder (zero-shot).")
    ap.add_argument("--images", required=True,
                    help="Folder with the target's reference images (or a single image)")
    ap.add_argument("--out", default="gallery.npy")
    args = ap.parse_args()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    embed_dim, image_size = 128, 224
    model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=True)
    if args.checkpoint:
        ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=True)
        embed_dim = ckpt.get("embed_dim", 128)
        image_size = ckpt.get("image_size", 224)
        model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False)
        model.load_state_dict(ckpt["model"])
        print(f"Loaded {args.checkpoint} (epoch {ckpt.get('epoch')}, val_acc {ckpt.get('val_acc')})")
    else:
        print("No checkpoint given -> zero-shot ImageNet features")
    model.eval().to(device)

    src = Path(args.images)
    paths = ([src] if src.is_file()
             else sorted(f for f in src.rglob("*") if f.suffix.lower() in IMG_EXTS))
    if not paths:
        raise SystemExit(f"No images found in {src}")

    tfm = build_transform(image_size, train=False)
    batch = torch.stack([load_image(p, tfm) for p in paths]).to(device)
    emb = model(batch).cpu().numpy().astype(np.float32)   # (V, D), L2-normalized

    np.save(args.out, emb)
    print(f"Enrolled {len(paths)} views -> {args.out}  shape={emb.shape}")
    print(f"gallery.npy size: {Path(args.out).stat().st_size/1024:.1f} KB "
          f"(this is the only artifact that leaves the client)")


if __name__ == "__main__":
    main()
