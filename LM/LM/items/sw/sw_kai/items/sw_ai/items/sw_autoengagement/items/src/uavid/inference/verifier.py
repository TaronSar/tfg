"""Deployment core: the ``Verifier`` -- the single source of truth for scoring.

Both threshold calibration and the end-to-end verify pipeline import from here,
so the MATCH score is guaranteed identical everywhere.

Runtime model (binary verification, NOT ranking)::

    enrolled gallery.npy  ->  mean prototype (L2-normalised)
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

from src.uavid.common.config_loader import load_encoder_config
from src.uavid.common.transforms import build_transform
from src.uavid.model import ProtoNetEncoder


class Verifier:
    """Load a trained ProtoNet + enrolled gallery and score crops against it."""

    def __init__(
        self, checkpoint: str | None, gallery: str | Path, device: str | None = None
    ) -> None:
        """Load the encoder and the enrolled gallery prototype.

        Args:
            checkpoint: Path to a trained ``.pth`` (or None for zero-shot).
            gallery: Path to the enrolled ``gallery.npy``.
            device: Torch device string (auto-detected if None).
        """
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")

        _enc = load_encoder_config()
        embed_dim, image_size = _enc["embed_dim"], _enc["image_size"]
        metric, normalize = "euclidean", True
        model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=True, l2_normalize=normalize)
        if checkpoint:
            ckpt = torch.load(checkpoint, map_location="cpu", weights_only=True)
            embed_dim = ckpt.get("embed_dim", _enc["embed_dim"])
            image_size = ckpt.get("image_size", _enc["image_size"])
            metric = ckpt.get("metric", "euclidean")
            normalize = ckpt.get("l2_normalize", True)
            model = ProtoNetEncoder(embed_dim=embed_dim, pretrained=False, l2_normalize=normalize)
            model.load_state_dict(ckpt["model"])
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
        self.gallery_emb = gal
        self.gallery_views = int(gal.shape[0])

    @torch.no_grad()
    def embed_pil(self, images: list[Image.Image]) -> torch.Tensor:
        """Embed a list of PIL images.

        Args:
            images: RGB PIL images to embed.

        Returns:
            Embedding tensor of shape ``(N, D)``.
        """
        if not images:
            return torch.empty(0)
        batch = torch.stack([self.tfm(im.convert("RGB")) for im in images])
        return self.model(batch.to(self.device))

    @torch.no_grad()
    def embed_paths(self, paths: list[Path]) -> torch.Tensor:
        """Embed a list of image paths.

        Args:
            paths: Image file paths to load and embed.

        Returns:
            Embedding tensor of shape ``(N, D)``.
        """
        imgs = [Image.open(p) for p in paths]
        try:
            return self.embed_pil(imgs)
        finally:
            for im in imgs:
                im.close()

    @torch.no_grad()
    def embed_bgr(self, crops_bgr: list[np.ndarray]) -> torch.Tensor:
        """Embed a list of OpenCV BGR crops (uint8 HxWx3).

        Args:
            crops_bgr: List of BGR images as ``uint8`` numpy arrays.

        Returns:
            Embedding tensor of shape ``(N, D)``.
        """
        pil = [Image.fromarray(c[:, :, ::-1]) for c in crops_bgr]
        return self.embed_pil(pil)

    def score(self, embeddings: torch.Tensor) -> np.ndarray:
        """Score each embedding against the enrolled prototype (cosine or -d^2).

        Args:
            embeddings: Query embeddings, shape ``(N, D)``.

        Returns:
            Float32 score array of shape ``(N,)``; higher means more similar.
        """
        if embeddings.numel() == 0:
            return np.empty(0, dtype=np.float32)
        if self.use_cosine:
            s = embeddings @ self.proto
        else:
            s = -((embeddings - self.proto) ** 2).sum(dim=-1)
        return s.cpu().numpy().astype(np.float32)

    def per_view_scores(self, embeddings: torch.Tensor) -> np.ndarray:
        """Score each query against every enrolled view separately (V x N).

        Args:
            embeddings: Query embeddings, shape ``(N, D)``.

        Returns:
            Float32 matrix of shape ``(V, N)`` where ``V`` is the number of
            enrolled views and ``N`` is the number of queries.
        """
        if embeddings.numel() == 0:
            return np.empty((self.gallery_views, 0), dtype=np.float32)
        if self.use_cosine:
            m = self.gallery_emb @ embeddings.t()
        else:
            m = -(torch.cdist(self.gallery_emb, embeddings) ** 2)
        return m.cpu().numpy().astype(np.float32)

    def gradcam_bgr(self, crop_bgr: np.ndarray) -> tuple[np.ndarray, float]:
        """Grad-CAM saliency for one BGR crop against the enrolled prototype.

        Backpropagates the MATCH score (cosine / -d^2) into the last
        convolutional feature map, highlighting the regions that pushed the
        embedding toward the enrolled identity.

        Args:
            crop_bgr: Input BGR crop as a ``uint8`` numpy array (HxWx3).

        Returns:
            ``(heatmap, score)`` -- ``heatmap`` is float32 ``HxW`` in ``[0, 1]``
            at the crop's native resolution; ``score`` is the scalar match score.
        """
        pil = Image.fromarray(crop_bgr[:, :, ::-1])
        x = self.tfm(pil.convert("RGB")).unsqueeze(0).to(self.device)

        activations: dict[str, torch.Tensor] = {}

        def _capture(_module, _inp, out):
            activations["value"] = out

        handle = self.model.features.register_forward_hook(_capture)
        try:
            self.model.zero_grad(set_to_none=True)
            emb = self.model(x)[0]
            if self.use_cosine:
                target = (emb * self.proto).sum()
            else:
                target = -((emb - self.proto) ** 2).sum()
            act = activations["value"]
            grads = torch.autograd.grad(target, act)[0]
        finally:
            handle.remove()

        weights = grads.mean(dim=(2, 3), keepdim=True)
        cam = F.relu((weights * act).sum(dim=1, keepdim=True))
        cam = F.interpolate(cam, size=crop_bgr.shape[:2], mode="bilinear", align_corners=False)[
            0, 0
        ]
        cam = cam - cam.min()
        peak = cam.max()
        if peak > 0:
            cam = cam / peak
        return cam.detach().cpu().numpy().astype(np.float32), float(target.detach())

    @property
    def score_name(self) -> str:
        """Name of the score used for decisions (``"cosine"`` or ``"-d^2"``)."""
        return "cosine" if self.use_cosine else "-d^2"
