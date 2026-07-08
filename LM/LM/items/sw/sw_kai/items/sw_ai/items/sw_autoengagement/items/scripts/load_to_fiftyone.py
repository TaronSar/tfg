"""Load a UAV identity-folder dataset into FiftyOne with split + identity labels.

Usage (on Vision server, NAS mounted)::

    PYTHONPATH=. uv run python scripts/load_to_fiftyone.py
        --data_root /mnt/Pool_IA/IA_Dataset/datasets/
            uav-few-shot-identification/uav_dataset_yolox_crops
        --name uav_yolox_crops

    # Or for the raw renders:
    PYTHONPATH=. uv run python scripts/load_to_fiftyone.py
        --data_root /mnt/Pool_IA/IA_Dataset/datasets/
            uav-few-shot-identification/uav_dataset_rendered
        --name uav_rendered

After the script prints "App running", open http://localhost:5151 in your browser.
If you are accessing from your local machine via SSH:
    ssh -L 5151:localhost:5151 <vision-server>
then open http://localhost:5151 on your local browser.
"""

from __future__ import annotations

import os
from pathlib import Path

import fire
from loguru import logger

from src.uavid.common.config_loader import load_fiftyone_config
from src.uavid.common.constants import IMG_EXTS


def main(
    data_root: str,
    name: str = "uav_dataset",
    splits: str = "train,val,enrollment",
    overwrite: bool = True,
) -> None:
    """Load a UAV identity-folder dataset into FiftyOne.

    Args:
        data_root: Dataset root containing split subdirectories
                   (train/, val/, enrollment/).
        name: FiftyOne dataset name (used for persistent storage in MongoDB).
        splits: Comma-separated splits to load.
        overwrite: If True, delete and recreate the dataset if it already exists.
    """
    # --- Connect to the department FiftyOne / MongoDB instance ---------------
    cfg = load_fiftyone_config()
    os.environ.setdefault("FIFTYONE_DATABASE_URI", cfg["database_uri"])
    logger.info(f"FiftyOne DB: {cfg['database_uri']}")

    import fiftyone as fo

    # --- Delete existing dataset if requested --------------------------------
    if overwrite and fo.dataset_exists(name):
        fo.delete_dataset(name)
        logger.info(f"Deleted existing dataset '{name}'")

    # --- Collect samples -----------------------------------------------------
    root = Path(data_root)
    split_list = [s.strip() for s in splits.split(",") if s.strip()]
    samples: list[fo.Sample] = []

    for split in split_list:
        split_dir = root / split
        if not split_dir.exists():
            logger.warning(f"Split directory not found, skipping: {split_dir}")
            continue
        identity_dirs = sorted(p for p in split_dir.iterdir() if p.is_dir())
        logger.info(f"Split '{split}': {len(identity_dirs)} identities")
        for identity_dir in identity_dirs:
            imgs = sorted(f for f in identity_dir.rglob("*") if f.suffix.lower() in IMG_EXTS)
            for img_path in imgs:
                s = fo.Sample(filepath=str(img_path))
                s["split"] = split
                s["identity"] = identity_dir.name
                s["is_negative"] = identity_dir.name.lower().startswith("neg_")
                samples.append(s)

    if not samples:
        logger.error(f"No images found under {root} for splits {split_list}")
        return

    logger.info(f"Total samples: {len(samples)}")

    # --- Create dataset and add samples --------------------------------------
    dataset = fo.Dataset(name=name)
    dataset.add_samples(samples)
    dataset.persistent = True  # survives between sessions in MongoDB
    logger.info(f"Dataset '{name}' saved to MongoDB (persistent=True)")

    # --- Launch the app ------------------------------------------------------
    logger.info("Launching FiftyOne app on http://localhost:5151 ...")
    logger.info("Press Ctrl+C to stop.")
    session = fo.launch_app(dataset, remote=True, port=5151)
    session.wait()


if __name__ == "__main__":
    fire.Fire(main)
