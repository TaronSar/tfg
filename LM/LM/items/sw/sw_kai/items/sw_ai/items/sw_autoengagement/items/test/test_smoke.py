"""Smoke tests for the few-shot UAV identification package.

Verifies the package imports and that the encoder produces a 128-d
L2-normalised embedding, and that the prototype / metric helpers behave.
"""

import torch

from src.uavid.model import (
    ProtoNetEncoder,
    attention_prototype,
    build_prototypes,
    euclidean_logits,
)


def test_package_imports():
    import src.uavid  # noqa: F401
    import src.uavid.dataset  # noqa: F401
    import src.uavid.eval  # noqa: F401
    import src.uavid.inference  # noqa: F401
    import src.uavid.model  # noqa: F401
    import src.uavid.train  # noqa: F401


def test_encoder_l2_normalised_embedding():
    model = ProtoNetEncoder(pretrained=False)
    x = torch.randn(2, 3, 224, 224)
    emb = model(x)
    assert emb.shape == (2, 128)
    norms = emb.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


def test_build_prototypes_mean():
    support = torch.randn(6, 128)
    labels = torch.tensor([0, 0, 0, 1, 1, 1])
    protos = build_prototypes(support, labels, n_way=2, normalize=True)
    assert protos.shape == (2, 128)
    norms = protos.norm(dim=-1)
    assert torch.allclose(norms, torch.ones_like(norms), atol=1e-5)


def test_attention_prototype_is_unit():
    query = torch.nn.functional.normalize(torch.randn(128), dim=0)
    gallery = torch.nn.functional.normalize(torch.randn(5, 128), dim=-1)
    proto = attention_prototype(query, gallery)
    assert proto.shape == (128,)
    assert abs(proto.norm().item() - 1.0) < 1e-5


def test_euclidean_logits_shape():
    q = torch.randn(4, 128)
    p = torch.randn(3, 128)
    logits = euclidean_logits(q, p)
    assert logits.shape == (4, 3)
    # logits are negative squared distances (<= 0)
    assert (logits <= 1e-4).all()
