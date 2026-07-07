"""Client-side enrollment: embed N reference images into ``gallery.npy``.

This is the privacy-critical step (Option A): only the resulting ``gallery.npy``
ever leaves the client's machine.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch

from src.uavid.common.config_loader import load_encoder_config
from src.uavid.common.constants import IMG_EXTS
from src.uavid.common.transforms import build_transform
from src.uavid.dataset import load_image
from src.uavid.model import ProtoNetEncoder


def _list_images(src: Path) -> list[Path]:
    """Return image paths under ``src`` (a single file or a directory)."""
    if src.is_file():
        return [src]
    return sorted(f for f in src.rglob("*") if f.suffix.lower() in IMG_EXTS)


@torch.no_grad()
def enroll_gallery(images: str | Path, out: str | Path = "gallery.npy",
                   checkpoint: str | None = None,
                   device: str | None = None) -> np.ndarray:
    """Embed reference images and save the L2-normalised gallery to ``out``.

    Args:
        images: Folder of reference images (or a single image).
        out: Destination ``.npy`` path for the gallery.
        checkpoint: Trained checkpoint (None -> zero-shot ImageNet features).
        device: Torch device string (auto-detected if None).

    Returns:
        The ``(V, D)`` gallery embedding array that was saved.

    Raises:
        SystemExit: If no images are found under ``images``.
    """
    device = device or ("cuda" if torch.cuda.is_available() else "cpu")
    _enc = load_encoder_config()
    embed_dim, image_size = _enc["embed_dim"], _enc["image_size"]
    model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=True)
    if checkpoint:
        ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
        embed_dim = ckpt.get("embed_dim", _enc["embed_dim"])
        image_size = ckpt.get("image_size", _enc["image_size"])
        model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False)
        model.load_state_dict(ckpt["model"])
    model.eval().to(device)

    paths = _list_images(Path(images))
    if not paths:
        raise SystemExit(f"No images found in {images}")

    tfm = build_transform(image_size, train=False)
    batch = torch.stack([load_image(p, tfm) for p in paths]).to(device)
    emb = model(batch).cpu().numpy().astype(np.float32)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    np.save(out, emb)
    return emb
