"""Builds the curation snapshot consumed by apply_curation stage/script."""
from __future__ import annotations

from pathlib import Path

import fire
from dotenv import load_dotenv

from src.ood.common.config_loader import (
    load_curation_config,
    load_fiftyone_dataset_name,
    load_paths_config,
)
from src.ood.cleaning.snapshot import export_curation_snapshot

load_dotenv()


def main(
    dataset_name: str | None = None,
    annotations_in: str | None = None,
    snapshot_out: str | None = None,
) -> None:
    """Freeze the final curation snapshot after CVAT pull stage.

    `annotations_in` is treated as a stage dependency to enforce order in DVC,
    while snapshot contents are sourced from the current FiftyOne dataset state.
    """
    # Load config defaults
    curation_cfg = load_curation_config()
    paths_cfg = load_paths_config()
    dataset_name = dataset_name or load_fiftyone_dataset_name()
    annotations_in = annotations_in or str(
        Path(paths_cfg["cvat_annotations_dir"]) / curation_cfg["cvat_annotations_file"]
    )
    snapshot_out = snapshot_out or str(
        Path(paths_cfg["curation_snapshot_dir"]) / curation_cfg["curation_snapshot_file"]
    )
    annotations_path = Path(annotations_in)
    if not annotations_path.exists():
        msg = f"Annotations artifact '{annotations_path}' not found."
        logger.error(msg)
        raise ValueError(msg)

    export_curation_snapshot(dataset_name, Path(snapshot_out))


if __name__ == "__main__":
    fire.Fire(main)
