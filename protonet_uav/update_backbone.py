# Save this on your Windows machine as: update_backbone.py
import torch
import torch.nn as nn
import torch.nn.functional as F
import torchvision.models as M

class StableEmbeddingBackbone(nn.Module):
    def __init__(self, embed_dim=128):
        super().__init__()
        # Load the stable MobileNetV3-Small features
        base = M.mobilenet_v3_small(pretrained=True)
        self.features = base.features
        self.pool = base.avgpool
        
        # Pure Linear projection layer (LayerNorm removed for TIDL stability)
        self.proj = nn.Linear(576, embed_dim)
        
    def forward(self, x):
        # Extract features, average pool, and flatten into a vector
        feat = self.pool(self.features(x)).flatten(1)
        emb = self.proj(feat)
        # Normalize over the unit sphere for stable cosine distances
        return F.normalize(emb, dim=-1)

if __name__ == "__main__":
    model = StableEmbeddingBackbone()
    model.eval()
    
    # Generate standard dummy crop input shape
    dummy_input = torch.randn(1, 3, 224, 224)
    
    # Export cleanly utilizing stable Opset 11
    torch.onnx.export(
        model, 
        dummy_input, 
        "backbone_stable.onnx", # Saved under a clear name
        opset_version=11,
        input_names=["image"], 
        output_names=["embedding"]
    )
    print("[+] Clean, hardware-compatible backbone exported successfully as 'backbone_stable.onnx'!")