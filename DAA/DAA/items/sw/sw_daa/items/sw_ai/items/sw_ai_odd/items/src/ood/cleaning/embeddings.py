"""Compute DINOv2 embeddings for AOT dataset images."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import torch
from loguru import logger
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from tqdm.auto import tqdm


class _ImageListDataset(Dataset):
    """Minimal dataset that loads images from absolute paths and applies a transform.

    Args:
        paths: Ordered list of absolute image file paths.
        transform: Torchvision transform applied to each PIL image.
    """

    def __init__(self, paths: list[Path], transform) -> None:
        self.paths = paths
        self.transform = transform

    def __len__(self) -> int:
        """Return the number of images in the dataset."""
        return len(self.paths)

    def __getitem__(self, idx: int) -> torch.Tensor:
        """Load, convert to RGB, and transform the image at *idx*.

        Args:
            idx: Zero-based sample index.

        Returns:
            Transformed image tensor.
        """
        img = Image.open(self.paths[idx]).convert("RGB")
        return self.transform(img)


def _load_dinov2_model(model_name: str, device: str) -> torch.nn.Module:
    """Load a DINOv2 backbone from ``timm`` in eval mode.

    Args:
        model_name: ``timm`` model identifier
            (e.g. ``"vit_small_patch14_dinov2.lvd142m"``).
        device: PyTorch device string (``"cuda"`` or ``"cpu"``).

    Returns:
        Model placed on *device* with classifier head removed.
    """
    import timm

    logger.info(f"Loading DINOv2 model [{model_name}] on {device} …")
    model = timm.create_model(model_name, pretrained=True, num_classes=0)
    return model.to(device).eval()


def _build_dinov2_transform(model: torch.nn.Module):
    """Build the preprocessing transform matching the model's expected input.

    Uses timm's ``resolve_model_data_config`` so that the image size,
    normalisation mean/std, and interpolation mode are all consistent with
    the model's pretrained configuration (e.g. 518×518 for DINOv2 ViT-S/14).

    Args:
        model: A timm model instance (after calling ``create_model``).

    Returns:
        A torchvision-compatible transform ready for inference.
    """
    from timm.data import create_transform, resolve_model_data_config

    data_config = resolve_model_data_config(model)
    return create_transform(**data_config, is_training=False)


def _build_embedding_loader(
    image_paths: list[Path],
    transform,
    batch_size: int,
    device: str,
) -> DataLoader:
    """Build a DataLoader for batch embedding inference.

    Args:
        image_paths: Absolute paths to images on disk.
        transform: Preprocessing transform compatible with the model.
        batch_size: Number of images per batch.
        device: PyTorch device string; used to decide ``pin_memory``.

    Returns:
        A non-shuffled ``DataLoader`` with the given transform applied.
    """
    dataset = _ImageListDataset(image_paths, transform)
    return DataLoader(
        dataset,
        batch_size=batch_size,
        num_workers=4,
        pin_memory=device != "cpu",
        shuffle=False,
    )


def _extract_features(
    model: torch.nn.Module,
    loader: DataLoader,
    device: str,
) -> np.ndarray:
    """Run forward passes and collect L2-normalised feature vectors.

    Args:
        model: DINOv2 backbone in eval mode (no classifier head).
        loader: DataLoader yielding batches of preprocessed image tensors.
        device: PyTorch device string.

    Returns:
        NumPy array of shape ``(N, embed_dim)`` with L2-normalised
        float32 feature vectors.
    """
    all_features: list[np.ndarray] = []
    with torch.no_grad():
        for batch in tqdm(loader, desc="DINOv2 embeddings", unit="batch"):
            batch = batch.to(device)
            features = model(batch)
            features = torch.nn.functional.normalize(features, dim=-1)
            all_features.append(features.cpu().numpy())
    return np.concatenate(all_features, axis=0)


def compute_dinov2_embeddings(
    image_paths: list[Path],
    model_name: str = "vit_small_patch14_dinov2.lvd142m",
    batch_size: int = 64,
    device: str | None = None,
) -> np.ndarray:
    """Compute DINOv2 feature embeddings for a list of images.

    Orchestrates model loading, transform construction from the model's
    own pretrained config, DataLoader construction, and batched inference.
    Each embedding is L2-normalised so that cosine similarity reduces to
    a dot product.

    Args:
        image_paths: Absolute paths to images on disk.
        model_name: ``timm`` model identifier for the DINOv2 backbone.
        batch_size: Inference batch size.
        device: PyTorch device string; auto-detected if ``None``.

    Returns:
        NumPy array of shape ``(len(image_paths), embed_dim)`` with
        L2-normalised float32 feature vectors.
    """
    if device is None:
        device = "cuda" if torch.cuda.is_available() else "cpu"

    model = _load_dinov2_model(model_name, device)
    transform = _build_dinov2_transform(model)
    loader = _build_embedding_loader(image_paths, transform, batch_size, device)
    embeddings = _extract_features(model, loader, device)

    logger.info(f"Computed embeddings: shape={embeddings.shape}, dtype={embeddings.dtype}")
    return embeddings
