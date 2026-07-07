"""Prepare the FiftyOne dataset for manual human curation.

This is stage ``03_cleanlab_to_fiftyone`` — the entry point of the
human-in-the-loop curation loop.  The FiftyOne dataset itself (with
DINOv2 embeddings, Cleanlab issue flags, and ``fiftyone.brain``
uniqueness/mistakenness/hardness scores) is created upstream by
``02_audit_dataset``.

This stage validates that the audited FiftyOne dataset exists and marks
the manual-review checkpoint as complete via a DVC-tracked stamp file.
Reviewers then inspect the dataset in FiftyOne and decide which samples
to tag as ``relabel``, ``to_Urban``, ``to_Non-urban``, ``to_Water``, or
``exclude``.

Typical curation loop after this stage::

     1. Open FiftyOne and review the audited dataset.
     2. Tag corrections directly (relabel / to_Urban / to_Non-urban /
         to_Water / exclude), OR push manual ``relabel`` tags to CVAT via
         ``curate.py push`` / ``curate.py pull``.
    3. Snapshot + apply:  dvc repro --force 04_apply_curation.

Requires ``fiftyone`` (``--group viz``) and ``FIFTYONE_DATABASE_URI``.

Usage (via DVC or directly)::

    FIFTYONE_DATABASE_URI=mongodb://192.168.2.1:27017/fiftyone \
    uv run --group viz python scripts/checkpoint_review_ready.py \
        --aot_root /path/to/aot-dataset \
        --audited_dir data/02_audit_dataset \
        --output_dir  data/03_cleanlab_to_fiftyone \
        --dataset_name ood_cleanlab_audit
"""
from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import fire
from loguru import logger

from src.ood.common.config_loader import load_fiftyone_dataset_name
from src.ood.common.fiftyone_utils import load_fiftyone_dataset


def main(
    output_dir: str,
    dataset_name: str | None = None,
    stamp_file: str | None = None,
) -> None:
    """Validate the audited FiftyOne dataset and mark manual review ready.
    
    All defaults are loaded from dvc_config.yaml. Override by passing explicitly.

    Args:
        aot_root: Root path to the AOT dataset on NAS (kept for interface
            symmetry with other stages; not otherwise required here).
        audited_dir: Directory produced by ``02_audit_dataset`` (kept for
            interface symmetry / provenance).
        output_dir: Output directory for the stage stamp file.
        dataset_name: Name of the FiftyOne dataset to validate.
            Defaults to config value.
        stamp_file: If provided, write a timestamp here after a successful
            run (used as a DVC output marker).
    """
    # Load config default for dataset_name
    dataset_name = dataset_name or load_fiftyone_dataset_name()
    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)

    dataset = load_fiftyone_dataset(dataset_name)
    logger.success(
        f"FiftyOne dataset '{dataset_name}' is ready for manual review "
        f"({len(dataset)} samples)."
    )
    logger.info(
        "Review in FiftyOne, then tag samples "
        "manually as relabel, to_*, or exclude before running curate.py "
        "push/pull/apply."
    )

    if stamp_file:
        stamp_path = Path(stamp_file)
        stamp_path.parent.mkdir(parents=True, exist_ok=True)
        stamp_path.write_text(
            datetime.now(tz=UTC).isoformat() + "\n",
            encoding="utf-8",
        )


if __name__ == "__main__":
    fire.Fire(main)
