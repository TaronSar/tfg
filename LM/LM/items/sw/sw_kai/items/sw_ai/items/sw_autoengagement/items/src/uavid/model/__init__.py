"""Encoder, prototypes, distance metrics and the attention aggregation head."""

from src.uavid.model.encoder import (
    BACKBONE_NORM,
    CLIPEncoder,
    DinoV2Encoder,
    ProtoNetEncoder,
    build_encoder,
)
from src.uavid.model.metrics import cosine_logits, euclidean_logits
from src.uavid.model.prototypes import attention_prototype, build_prototypes

__all__ = [
    "ProtoNetEncoder",
    "DinoV2Encoder",
    "CLIPEncoder",
    "build_encoder",
    "BACKBONE_NORM",
    "euclidean_logits",
    "cosine_logits",
    "build_prototypes",
    "attention_prototype",
]
