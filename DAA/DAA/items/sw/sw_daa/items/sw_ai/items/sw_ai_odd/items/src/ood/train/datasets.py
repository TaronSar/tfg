"""PyTorch Dataset classes for the OOD pipeline."""
from __future__ import annotations

from pathlib import Path

import torch
from PIL import Image
from torch.utils.data import Dataset
from torchvision import transforms

from src.ood.common.io import read_jsonl
from src.ood.common.transforms import CLASS_TO_IDX
from src.ood.preprocessing.corruptions import corrupted_full_path


class IDDataset(Dataset):
    """In-distribution dataset: loads raw AOT frames with full preprocessing.

    Applies the resize → grayscale → optional augmentation → normalisation
    pipeline defined by *transform*.
    """

    def __init__(self, jsonl_path: Path, aot_root: Path, transform: transforms.Compose) -> None:
        self.records = read_jsonl(jsonl_path)
        self.aot_root = Path(aot_root)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, int]:
        rec = self.records[i]
        img = Image.open(self.aot_root / rec["path"]).convert("RGB")
        x = self.transform(img)
        y = CLASS_TO_IDX[rec["label"]]
        return x, y


class CorruptedSubset(Dataset):
    """In-memory subset of pre-generated corrupted full frames.

    Receives a pre-filtered list of records (e.g. one corruption type at one
    severity level) so callers can compute per-group OOD metrics.  Each record
    carries the AOT-relative source frame ``path`` plus ``type``/``severity``;
    the corresponding corrupted full frame is resolved via
    :func:`corrupted_full_path`.
    """

    def __init__(
        self,
        records: list[dict],
        corrupted_full_img_dir: Path,
        transform: transforms.Compose,
    ) -> None:
        self.records = records
        self.corrupted_full_img_dir = Path(corrupted_full_img_dir)
        self.transform = transform

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, i: int) -> tuple[torch.Tensor, int]:
        rec = self.records[i]
        img_path = corrupted_full_path(
            rec["path"], rec["type"], int(rec["severity"]), self.corrupted_full_img_dir
        )
        img = Image.open(img_path).convert("RGB")
        x = self.transform(img)
        y = CLASS_TO_IDX[rec["label"]]
        return x, y
