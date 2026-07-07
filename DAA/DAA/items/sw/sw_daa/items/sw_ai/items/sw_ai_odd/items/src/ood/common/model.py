"""ResNet-18 classifier builder for the OOD pipeline."""
from __future__ import annotations

import torch.nn as nn
from torchvision import models
from torchvision.models import ResNet18_Weights

from .transforms import CLASSES


def build_classifier(
    num_classes: int = len(CLASSES),
    freeze: bool = True,
    unfreeze: tuple[str, ...] = ("layer3", "layer4", "fc"),
) -> nn.Module:
    """ImageNet-pretrained ResNet-18 with a fresh ``num_classes`` head.

    Args:
        num_classes: Number of output classes.  Defaults to ``len(CLASSES)``.
        freeze: When ``True`` (default), all backbone parameters are frozen
            except those whose name starts with a prefix in *unfreeze*.
            When ``False``, the entire network is trainable.
        unfreeze: Tuple of parameter-name prefixes to leave trainable when
            *freeze* is ``True``.  Ignored when *freeze* is ``False``.

    Returns:
        ``nn.Module`` ready for fine-tuning.
    """
    m = models.resnet18(weights=ResNet18_Weights.DEFAULT)
    in_f = m.fc.in_features
    m.fc = nn.Linear(in_f, num_classes)
    if freeze:
        for p in m.parameters():
            p.requires_grad = False
        for name, p in m.named_parameters():
            if any(name.startswith(b) for b in unfreeze):
                p.requires_grad = True
    return m
