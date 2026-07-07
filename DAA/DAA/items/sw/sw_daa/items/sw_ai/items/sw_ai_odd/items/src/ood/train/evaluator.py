"""Evaluation helpers for classification and OOD detection (pure logic, no MLflow)."""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import torch
import torch.nn as nn
from sklearn.metrics import roc_auc_score
from torch.utils.data import DataLoader
from tqdm import tqdm


@torch.no_grad()
def predict_loader(
    model: nn.Module,
    loader: DataLoader,
    device: str = "cpu",
) -> tuple[np.ndarray, np.ndarray]:
    """Run *model* over *loader* and return ground-truth / prediction arrays.

    Args:
        model: Classifier ``nn.Module`` in eval mode (or set to eval here).
        loader: DataLoader yielding ``(x, y)`` batches.
        device: PyTorch device string.

    Returns:
        A 2-tuple ``(y_true, y_pred)`` of integer class-index arrays.
    """
    ys, ps = [], []
    model.eval()
    for x, y in tqdm(loader, desc="Predicting", unit="batch", leave=False):
        x = x.to(device)
        ps.append(model(x).argmax(1).cpu().numpy())
        ys.append(y.numpy() if isinstance(y, torch.Tensor) else np.array(y))
    return np.concatenate(ys), np.concatenate(ps)


@torch.no_grad()
def score_loader(
    detector_fn: Callable[[torch.Tensor], torch.Tensor],
    loader: DataLoader,
    device: str = "cpu",
) -> np.ndarray:
    """Apply ``detector_fn(x_batch) → 1-D scores`` over a DataLoader.

    Args:
        detector_fn: Callable that accepts a batched tensor and returns a
            1-D score tensor (higher = more in-distribution).
        loader: DataLoader yielding ``(x, ...)`` batches.
        device: PyTorch device string.

    Returns:
        Concatenated 1-D NumPy score array over all batches.
    """
    out: list[np.ndarray] = []
    for batch in tqdm(loader, desc="Scoring", unit="batch", leave=False):
        x = batch[0].to(device)
        out.append(detector_fn(x).detach().cpu().numpy())
    return np.concatenate(out)


def auroc_fpr95(s_id: np.ndarray, s_ood: np.ndarray) -> tuple[float, float]:
    """Compute AUROC and FPR@TPR95 given ID and OOD score arrays.

    Higher score = more in-distribution (caller must negate energy if needed).

    Args:
        s_id: 1-D score array for in-distribution samples.
        s_ood: 1-D score array for OOD samples.

    Returns:
        A 2-tuple ``(auroc, fpr95)`` where *auroc* is the area under the ROC
        curve and *fpr95* is the false-positive rate at 95 % true-positive rate.
    """
    y_true = np.concatenate([np.ones_like(s_id), np.zeros_like(s_ood)])
    y_score = np.concatenate([s_id, s_ood])
    auroc = float(roc_auc_score(y_true, y_score))
    # Threshold at the 5th percentile of ID scores → 95% of ID samples are above it.
    thr = float(np.quantile(s_id, 0.05))
    # FPR95: fraction of OOD samples that exceed the threshold (false positives).
    fpr95 = float((s_ood > thr).mean())
    return auroc, fpr95
