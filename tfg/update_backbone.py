import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as M
from pathlib import Path


class StableV2EmbeddingBackbone(nn.Module):
    def __init__(self, embed_dim=128):
        super().__init__()
        # MobileNetV2 avoids several ops that can be problematic on edge runtimes.
        base = M.mobilenet_v2(weights=M.MobileNet_V2_Weights.DEFAULT)
        self.features = base.features

        # MobileNetV2 outputs (N, 1280, 7, 7) before pooling for 224x224 inputs.
        self.pool = nn.AdaptiveAvgPool2d((1, 1))

        # Project pooled 1280-D features to the target embedding space.
        self.proj = nn.Linear(1280, embed_dim)

    def forward(self, x):
        x = self.features(x)
        feat = self.pool(x).flatten(1)
        emb = self.proj(feat)
        return F.normalize(emb, dim=-1)


if __name__ == "__main__":
    print("[+] Initializing MobileNetV2 stable architecture conversion...")
    model = StableV2EmbeddingBackbone()
    model.eval()

    dummy_input = torch.randn(1, 3, 224, 224)
    output_path = Path(__file__).resolve().parent / "backbone_v2_stable.onnx"

    torch.onnx.export(
        model,
        dummy_input,
        str(output_path),
        opset_version=11,
        input_names=["image"],
        output_names=["embedding"],
        dynamo=False,
    )
    print(f"[+] Success! Clean model graph exported as '{output_path}'")
