r"""CLI: build the small-crop exclusion list (no files are moved or deleted).

Writes a JSON listing the train/val crops below ``--min_px`` so the dataset
loader can skip them. The dataset folder is never mutated, keeping its hash
stable across runs.

Usage::

    PYTHONPATH=. uv run python scripts/filter_small_crops.py \\
        --data_root /mnt/Pool_IA/IA_Dataset/datasets/ \\
            uav-few-shot-identification/uav_dataset_yolox_crops \\
        --min_px 30 --out data/annotations/excluded_crops.json
"""

from __future__ import annotations

import fire
from loguru import logger

from src.uavid.preprocessing.filter_crops import build_exclusion, write_exclusion


def main(
    data_root: str,
    out: str = "data/annotations/excluded_crops.json",
    min_px: int = 30,
    splits: str = "train,val",
) -> None:
    """Scan the dataset and write the small-crop exclusion JSON.

    Args:
        data_root: Dataset root containing the split subdirectories.
        out: Destination JSON path for the exclusion list.
        min_px: Minimum allowed shorter-side size in pixels.
        splits: Comma-separated splits to scan (default ``train,val``).
    """
    split_tuple = tuple(s.strip() for s in splits.split(",") if s.strip())
    report = build_exclusion(data_root, min_px=min_px, splits=split_tuple)
    write_exclusion(report, out)
    logger.info(
        f"Checked {report['n_checked']} crops in {split_tuple}; "
        f"{report['n_excluded']} below {min_px}px excluded -> {out}"
    )


if __name__ == "__main__":
    fire.Fire(main)
