"""Apply curation decisions from a snapshot file to produce curated data.

Consumes a previously exported ``curation_snapshot.jsonl`` and applies
its exclusions/relabels to the audited JSONL and embeddings to produce
curated outputs for downstream DVC stages.

Usage (via DVC or directly)::

    uv run --group viz python scripts/apply_curation.py \
        --audited_dir  data/02_audit_dataset \
        --output_dir   data/04_apply_curation \
        --snapshot_file data/03d_build_curation_snapshot/curation_snapshot.jsonl
"""
from __future__ import annotations

import json
from pathlib import Path

import fire
import numpy as np
from loguru import logger

from src.ood.cleaning.snapshot import EXCLUDE_TAG
from src.ood.common.config_loader import load_curation_config, load_paths_config
from src.ood.common.constants import SPLIT_NAMES
from src.ood.common.io import read_jsonl, write_jsonl
from src.ood.dataset.clip_classifier import filter_coco_by_frames


def _build_curation_index(snapshot_rows: list[dict]) -> tuple[set[str], dict[str, str]]:
    """Derive exclusion and relabel maps from snapshot rows.

    Args:
        snapshot_rows: Rows produced by :func:`export_curation_snapshot`.

    Returns:
        Tuple of (excluded_filenames, relabel_map) where
        ``excluded_filenames`` is a set of image filenames to remove, and
        ``relabel_map`` maps image filename to the new label string.
    """
    exclusions: set[str] = {r["filename"] for r in snapshot_rows if r["exclude"]}
    logger.info(f"Curation: {len(exclusions)} samples tagged '{EXCLUDE_TAG}'")

    relabels: dict[str, str] = {
        r["filename"]: r["relabel"]
        for r in snapshot_rows
        if r["relabel"] and r["filename"] not in exclusions
    }
    logger.info(f"Curation: {len(relabels)} samples with relabel decisions")
    return exclusions, relabels


def _apply_to_split(
    records: list[dict],
    embeddings: np.ndarray,
    exclusions: set[str],
    relabels: dict[str, str],
    split_name: str,
) -> tuple[list[dict], np.ndarray]:
    """Apply exclusions and relabels to a single split.

    Args:
        records: JSONL records for this split.
        embeddings: Embedding array aligned to records.
        exclusions: Set of image filenames to exclude.
        relabels: Dict mapping image filename to corrected label.
        split_name: Split identifier for logging.

    Returns:
        Tuple of (filtered records, filtered embeddings).
    """
    keep_indices: list[int] = []
    curated_records: list[dict] = []
    n_excluded = 0
    n_relabeled = 0

    for i, rec in enumerate(records):
        img_name = rec["img_name"]
        if img_name in exclusions:
            n_excluded += 1
            continue
        keep_indices.append(i)
        if img_name in relabels:
            rec = {**rec, "label": relabels[img_name]}
            n_relabeled += 1
        curated_records.append(rec)

    curated_emb = embeddings[keep_indices] if keep_indices else np.empty((0, embeddings.shape[1]))

    logger.info(
        f"{split_name}: {len(records)} → {len(curated_records)} "
        f"(excluded {n_excluded}, relabeled {n_relabeled})"
    )
    return curated_records, curated_emb


def main(
    audited_dir: str,
    output_dir: str,
    snapshot_file: str | None = None,
    background_dir: str | None = None,
) -> None:
    """Apply curation decisions from snapshot to the audited dataset.

    Filters and relabels audited JSONL + embeddings deterministically
    using a pre-exported curation snapshot file.  The linked detection crops
    COCO JSONs produced by stage 01 are propagated in lockstep: crops whose
    source frame was excluded during curation are dropped, while background
    relabels never touch the detection ground truth.

    All defaults are loaded from dvc_config.yaml. Override snapshot_file by passing explicitly.

    Args:
        audited_dir: Directory with audited JSONL and embeddings.
        output_dir: Output directory for curated JSONL, embeddings, and
            related artifacts.
        snapshot_file: Source ``curation_snapshot.jsonl`` file containing
            curation decisions exported from FiftyOne/Mongo.
        background_dir: Directory holding the stage-01 linked crops COCO
            JSONs (``{split}_crops.json``). Defaults to
            ``paths.background_classification_dir``.
    """
    curation_cfg = load_curation_config()
    paths_cfg = load_paths_config()

    audited_dir_p = Path(audited_dir)
    output_dir_p = Path(output_dir)
    output_dir_p.mkdir(parents=True, exist_ok=True)

    background_dir = background_dir or paths_cfg["background_classification_dir"]
    background_dir_p = Path(background_dir)

    snapshot_file = snapshot_file or str(
        Path(paths_cfg["curation_snapshot_dir"]) / curation_cfg["curation_snapshot_file"]
    )
    snapshot_path = Path(snapshot_file)
    if not snapshot_path.exists():
        msg = (
            f"Snapshot file '{snapshot_path}' not found. "
            "Run curate.py snapshot before apply."
        )
        logger.error(msg)
        raise ValueError(msg)

    snapshot_rows = read_jsonl(snapshot_path)
    exclusions, relabels = _build_curation_index(snapshot_rows)

    for name in SPLIT_NAMES:
        records = read_jsonl(audited_dir_p / f"{name}.jsonl")
        embeddings = np.load(audited_dir_p / f"embeddings_{name}.npy")

        curated_records, curated_emb = _apply_to_split(
            records, embeddings, exclusions, relabels, name,
        )

        write_jsonl(output_dir_p / f"{name}.jsonl", curated_records)
        np.save(output_dir_p / f"embeddings_{name}.npy", curated_emb)

        # Propagate exclusions to the linked detection crops COCO JSON.
        crops_in = background_dir_p / f"{name}_crops.json"
        crops_out = output_dir_p / f"{name}_crops.json"
        if crops_in.exists():
            retained_frames = {rec["path"] for rec in curated_records}
            crops_coco = filter_coco_by_frames(crops_in, retained_frames)
            with crops_out.open("w", encoding="utf-8") as f:
                json.dump(crops_coco, f)
            logger.info(
                f"{name}: crops {crops_in.name} → {len(crops_coco['images']):,} crops "
                f"/ {len(retained_frames):,} frames"
            )
        else:
            logger.warning(f"{name}: no linked crops JSON found at {crops_in}")

    logger.success("Curation applied successfully.")


if __name__ == "__main__":
    fire.Fire(main)
