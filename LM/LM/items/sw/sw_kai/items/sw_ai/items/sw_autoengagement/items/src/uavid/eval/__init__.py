"""Open-set evaluation, k-shot sweeps and threshold calibration."""

from src.uavid.eval.openset import (
    embed_paths,
    evaluate_openset,
    roc_auc,
    tpr_at_fpr,
)

__all__ = ["embed_paths", "roc_auc", "tpr_at_fpr", "evaluate_openset"]
