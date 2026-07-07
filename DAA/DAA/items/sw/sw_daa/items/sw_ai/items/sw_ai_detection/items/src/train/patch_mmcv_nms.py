import torch
import torchvision
from mmcv.ops.nms import NMSop  # type: ignore[reportMissingImports]


@staticmethod  # type: ignore[misc]
def _patched_forward(ctx, bboxes, scores, iou_threshold, offset, score_threshold, max_num):
    """NMS forward using ``torchvision.ops.nms`` as a drop-in replacement."""
    keep = torchvision.ops.nms(bboxes, scores, iou_threshold)
    if score_threshold > 0:
        keep = keep[scores[keep] > score_threshold]
    if max_num > 0:
        keep = keep[:max_num]
    return keep


try:
    _test = torch.tensor([[0, 0, 1, 1]], dtype=torch.float32, device="cuda")
    NMSop.apply(_test, torch.tensor([0.9], dtype=torch.float32, device="cuda"), 0.5, 0, 0, 0)
except RuntimeError:
    NMSop.forward = _patched_forward
    print("[patch_mmcv_nms] Patched mmcv NMS -> torchvision.ops.nms")
