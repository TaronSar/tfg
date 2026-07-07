"""Deployment core: shared verification primitives.

This module is the single source of truth for how the deployed device turns a
crop into a yes/no decision against an enrolled gallery. Both the threshold
calibration tool and the end-to-end verify pipeline import from here so the
scoring is guaranteed identical to `src.identify`.

Runtime model (binary verification, NOT ranking):
    enrolled gallery.npy  ->  mean prototype (L2-normalized)
    incoming crop         ->  embedding
    score = cosine(embedding, prototype)
    MATCH if score >= threshold else UNKNOWN
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from PIL import Image

from src.dataset import build_transform
from src.model import ProtoNetEncoder


class Verifier:
    """Loads a trained ProtoNet + enrolled gallery and scores crops against it."""

    def __init__(self, checkpoint: str | None, gallery: str | Path,
                 device: str | None = None):
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        embed_dim, image_size = 128, 224
        metric, normalize = "euclidean", True
        model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=True,
                                l2_normalize=normalize)
        if checkpoint:
            ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
            embed_dim = ckpt.get("embed_dim", 128)
            image_size = ckpt.get("image_size", 224)
            metric = ckpt.get("metric", "euclidean")
            normalize = ckpt.get("l2_normalize", True)
            model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False,
                                    l2_normalize=normalize)
            model.load_state_dict(ckpt["model"])
            print(f"Loaded {checkpoint} "
                  f"(epoch {ckpt.get('epoch')}, val_acc {ckpt.get('val_acc')})")
        else:
            print("No checkpoint -> zero-shot ImageNet features")
        model.eval().to(self.device)

        self.model = model
        self.image_size = image_size
        self.metric = metric
        self.normalize = normalize
        self.use_cosine = (metric == "cosine") or normalize
        self.tfm = build_transform(image_size, train=False)

        gal = torch.from_numpy(np.load(str(gallery))).float().to(self.device)
        if normalize:
            gal = F.normalize(gal, p=2, dim=-1)
            self.proto = F.normalize(gal.mean(dim=0), p=2, dim=0)
        else:
            self.proto = gal.mean(dim=0)
        # Per-enrollment-image embeddings kept un-collapsed so callers can score
        # each enrolled view (angle) against queries individually.
        self.gallery_emb = gal
        self.gallery_views = int(gal.shape[0])

    @torch.no_grad()
    def embed_pil(self, images: list[Image.Image]) -> torch.Tensor:
        if not images:
            return torch.empty(0)
        batch = torch.stack([self.tfm(im.convert("RGB")) for im in images])
        return self.model(batch.to(self.device))

    @torch.no_grad()
    def embed_paths(self, paths: list[Path]) -> torch.Tensor:
        imgs = [Image.open(p) for p in paths]
        try:
            return self.embed_pil(imgs)
        finally:
            for im in imgs:
                im.close()

    @torch.no_grad()
    def embed_bgr(self, crops_bgr: list[np.ndarray]) -> torch.Tensor:
        """Embed OpenCV BGR crops (np.uint8 HxWx3)."""
        pil = [Image.fromarray(c[:, :, ::-1]) for c in crops_bgr]
        return self.embed_pil(pil)

    def score(self, embeddings: torch.Tensor) -> np.ndarray:
        """Cosine (or -d^2) score of each embedding against the prototype."""
        if embeddings.numel() == 0:
            return np.empty(0, dtype=np.float32)
        if self.use_cosine:
            s = embeddings @ self.proto
        else:
            s = -((embeddings - self.proto) ** 2).sum(dim=-1)
        return s.cpu().numpy().astype(np.float32)

    def per_view_scores(self, embeddings: torch.Tensor) -> np.ndarray:
        """Score each query embedding against every enrolled view separately.

        Unlike `score`, this does NOT collapse the gallery into a single
        prototype. It returns the (V, N) matrix of per-enrollment-image scores
        (V enrolled views x N query embeddings), using the same metric as the
        MATCH decision (cosine similarity, or -squared-Euclidean distance).
        """
        if embeddings.numel() == 0:
            return np.empty((self.gallery_views, 0), dtype=np.float32)
        if self.use_cosine:
            m = self.gallery_emb @ embeddings.t()           # (V, N)
        else:
            m = -torch.cdist(self.gallery_emb, embeddings) ** 2  # (V, N)
        return m.cpu().numpy().astype(np.float32)

    def gradcam_bgr(self, crop_bgr: np.ndarray) -> tuple[np.ndarray, float]:
        """Grad-CAM saliency for one BGR crop against the enrolled prototype.

        Backpropagates the same score used for the MATCH decision
        (cosine / -d^2) into the last convolutional feature map of the
        backbone, so the resulting heatmap highlights the regions of the UAV
        that pushed the embedding toward the enrolled identity.

        Returns:
            (heatmap, score) where heatmap is float32 HxW in [0, 1] at the
            crop's native resolution and score is the scalar match score.
        """
        pil = Image.fromarray(crop_bgr[:, :, ::-1])
        x = self.tfm(pil.convert("RGB")).unsqueeze(0).to(self.device)

        activations: dict[str, torch.Tensor] = {}

        def _capture(_module, _inp, out):
            activations["value"] = out

        handle = self.model.features.register_forward_hook(_capture)
        try:
            self.model.zero_grad(set_to_none=True)
            emb = self.model(x)[0]                       # (D,)
            if self.use_cosine:
                target = (emb * self.proto).sum()
            else:
                target = -((emb - self.proto) ** 2).sum()
            act = activations["value"]                   # (1, C, h, w)
            grads = torch.autograd.grad(target, act)[0]  # (1, C, h, w)
        finally:
            handle.remove()

        weights = grads.mean(dim=(2, 3), keepdim=True)   # (1, C, 1, 1)
        cam = F.relu((weights * act).sum(dim=1, keepdim=True))  # (1, 1, h, w)
        cam = F.interpolate(cam, size=crop_bgr.shape[:2],
                            mode="bilinear", align_corners=False)[0, 0]
        cam = cam - cam.min()
        peak = cam.max()
        if peak > 0:
            cam = cam / peak
        return cam.detach().cpu().numpy().astype(np.float32), float(target.detach())

    @property
    def score_name(self) -> str:
        return "cosine" if self.use_cosine else "-d^2"
