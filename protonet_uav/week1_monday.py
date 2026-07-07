import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as models
from torchvision.models import MobileNet_V3_Small_Weights
import onnxruntime as ort
import numpy as np

class EmbeddingBackbone(nn.Module):
    """
    MobileNetV3-Small stripped of its classifier, with a 128-dim
    projection head. Outputs an L2-normalised embedding vector.
    
    Forward pass:
        input  : (B, 3, 224, 224)  float32, values in [0, 1]
        output : (B, 128)           float32, L2 unit norm
    """
    def __init__(self, embed_dim: int = 128):
        super().__init__()
        base = models.mobilenet_v3_small(
            weights=MobileNet_V3_Small_Weights.IMAGENET1K_V1
        )
        self.features = base.features          # conv stack → [B, 576, 7, 7]
        self.pool     = base.avgpool           # → [B, 576, 1, 1]
        self.proj     = nn.Sequential(
            nn.Flatten(),                      # → [B, 576]
            nn.Linear(576, embed_dim),
            nn.LayerNorm(embed_dim),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = self.features(x)
        x = self.pool(x)
        x = self.proj(x)
        return F.normalize(x, dim=-1)          # L2 norm → unit sphere


# ── Build ──────────────────────────────────────────────────────────────────
backbone = EmbeddingBackbone(embed_dim=128)
backbone.eval()

# ── Export ─────────────────────────────────────────────────────────────────
dummy = torch.randn(1, 3, 224, 224)

torch.onnx.export(
    backbone,
    dummy,
    "backbone_fp32.onnx",
    opset_version=11,
    dynamo=False,
    input_names=["image"],
    output_names=["embedding"],
)
print("Exported backbone_fp32.onnx")

# ── Verify ─────────────────────────────────────────────────────────────────
session = ort.InferenceSession(
    "backbone_fp32.onnx",
    providers=["CPUExecutionProvider"]
)

inp  = np.random.randn(1, 3, 224, 224).astype(np.float32)
out  = session.run(["embedding"], {"image": inp})[0]

print(f"Output shape : {out.shape}")           # expect (1, 128)
print(f"L2 norm      : {np.linalg.norm(out):.6f}")  # expect ≈ 1.000000
print(f"Min / Max    : {out.min():.4f} / {out.max():.4f}")