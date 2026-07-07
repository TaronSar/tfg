"""CLI entry point: generate corrupted OOD images from background-classification data.

Assigns each image one corruption type (round-robin over the active corruption types)
and applies it at the configured severity levels.  The ``severity_filter`` parameter
controls which corruption types are generated and from which minimum severity level,
using the same format as ``ood_filter`` in the training stage.

Full-size corrupted frames are written in an AOT-mirrored,
split-independent layout:

    <corrupted_full_img_dir>/<part>/Images/<flight>/<frame_stem>_<type>_<sev>.png

while the per-split annotation manifests stay local:

    <output_dir>/
        {train,val,test}/
            dataset.jsonl

Usage (via DVC or directly)::

    uv run python scripts/create_corrupted.py \\
        --aot_root /path/to/aot-dataset \\
        --bg_class_dir data/04_apply_curation \\
        --output_dir data/05_create_corrupted_full \\
        --corrupted_full_img_dir /mnt/Pool_IA/IA_Dataset/datasets/airborne_corrupted_images/full \\
        --severity_filter "all:1" \\
        --num_workers 8
"""

from __future__ import annotations

import random
from pathlib import Path

import fire
from joblib import Parallel, delayed
from joblib.externals.loky import get_reusable_executor
from loguru import logger
from tqdm import tqdm

from src.ood.common.io import parse_ood_filter, read_jsonl, write_jsonl
from src.ood.common.transforms import SEVERITIES
from src.ood.preprocessing.corruptions import _worker_init, process_single_image


def _process_split(
    split_name: str,
    records: list[dict],
    output_dir: Path,
    corrupted_full_img_dir: Path,
    aot_root: Path,
    severity_map: dict[str, list[int]],
    num_workers: int,
    subsample_fraction: float = 1.0,
    seed: int = 0,
) -> None:
    """Process one dataset split: assign one corruption per image (round-robin).

    Images are distributed round-robin over the active corruption types (those
    present in *severity_map*).  Each image is processed at the severity levels
    defined for its assigned corruption type.  Full-size corrupted frames are
    written under *corrupted_full_img_dir*; the manifest is written to
    ``output_dir / split_name / dataset.jsonl`` (local).

    When *subsample_fraction* < 1.0, a deterministic random subset of
    *records* is selected before corruption.  This keeps the total output
    volume manageable (e.g. 0.2 × 5 severities ≈ 1× input count).

    Args:
        split_name: One of ``"train"``, ``"val"``, or ``"test"``.
        records: JSONL records from the background-classification split.
        output_dir: Root local directory for the per-split manifest.
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        aot_root: Root path to the AOT dataset.
        severity_map: Mapping from corruption name to the list of severity
            levels to generate, e.g. ``{"fog": [3, 4, 5], "darken": [1, 2, 3, 4, 5]}``.
        num_workers: Number of parallel joblib/loky workers.
        subsample_fraction: Fraction of records to keep (0.0–1.0].
        seed: Random seed for reproducible subsampling.
    """
    if subsample_fraction < 1.0:
        k = max(1, int(len(records) * subsample_fraction))
        rng = random.Random(seed)
        records = rng.sample(records, k)
        logger.info(f"  [{split_name}] Subsampled to {k:,} records")

    split_dir = output_dir / split_name
    split_dir.mkdir(parents=True, exist_ok=True)
    active = list(severity_map.keys())
    n_corr = len(active)
    logger.info(
        f"  [{split_name}] {len(records):,} images × {n_corr} active corruption types (round-robin)"
    )

    jobs = (
        delayed(process_single_image)(
            rec=rec,
            corruption_name=active[i % n_corr],
            corrupted_full_img_dir=corrupted_full_img_dir,
            aot_root=aot_root,
            severities=severity_map[active[i % n_corr]],
        )
        for i, rec in enumerate(records)
    )
    parallel = Parallel(
        n_jobs=num_workers,
        backend="loky",
        initializer=_worker_init,
        return_as="generator_unordered",
    )
    results = list(
        tqdm(
            parallel(jobs),
            total=len(records),
            desc=split_name,
            unit="img",
        )
    )

    flat: list[dict] = [r for batch in results if batch for r in batch]
    jsonl_path = split_dir / "dataset.jsonl"
    write_jsonl(jsonl_path, flat)
    logger.info(f"  [{split_name}] {len(flat):,} records → {jsonl_path}")


def create_corrupted(
    aot_root: Path,
    bg_class_dir: Path,
    output_dir: Path,
    corrupted_full_img_dir: Path,
    *,
    severity_filter: str = "all:1",
    num_workers: int = 8,
    subsample_fraction: float = 1.0,
    splits: tuple[str, ...] = ("train", "val", "test"),
    seed: int = 0,
) -> None:
    """Apply image corruptions to the configured background-classification splits.

    Each image is assigned one corruption type via round-robin over the active
    types defined by *severity_filter*, and processed at the corresponding
    severity levels.  Full-size corrupted frames are written under
    *corrupted_full_img_dir*; per-split manifests are written under *output_dir*.

    When *subsample_fraction* < 1.0 a deterministic random subset of each
    split is selected before corruption, reducing total output volume.

    Existing files are never deleted; re-running with a different filter only
    adds new files.

    Args:
        aot_root: Root path to the AOT dataset.
        bg_class_dir: Directory containing ``train.jsonl``, ``val.jsonl``,
            and ``test.jsonl`` produced by the curation stage.
        output_dir: Root local directory for per-split manifests.
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        severity_filter: Controls which corruption types are generated and
            from which minimum severity, using the same format as
            ``ood_filter``.  Examples: ``"all:1"`` (all types, sev 1–5),
            ``"all:3"`` (all types, sev 3–5), ``"fog:3,darken:1"`` (fog
            sev 3–5 and darken sev 1–5 only).
        num_workers: Number of parallel joblib workers for image processing.
        subsample_fraction: Fraction of each split to corrupt (0.0–1.0].
        splits: Which splits to corrupt.
        seed: Random seed for reproducible subsampling.
    """
    filt = parse_ood_filter(severity_filter)
    severity_map: dict[str, list[int]] = {
        ctype: list(range(min_sev, max(SEVERITIES) + 1)) for ctype, min_sev in filt.items()
    }
    logger.info(
        f"Severity filter: {severity_filter}  |  workers: {num_workers}"
        f"  |  subsample: {subsample_fraction:.0%}  |  splits: {splits}"
    )
    logger.info(f"Corrupted full-image root: {corrupted_full_img_dir}")
    for ctype, sevs in severity_map.items():
        logger.info(f"  {ctype}: severities {sevs}")

    output_dir.mkdir(parents=True, exist_ok=True)
    corrupted_full_img_dir.mkdir(parents=True, exist_ok=True)

    for split_name in splits:
        jsonl_path = bg_class_dir / f"{split_name}.jsonl"
        if not jsonl_path.exists():
            logger.warning(f"  {jsonl_path} not found — skipping {split_name}")
            continue
        records = read_jsonl(jsonl_path)
        _process_split(
            split_name=split_name,
            records=records,
            output_dir=output_dir,
            corrupted_full_img_dir=corrupted_full_img_dir,
            aot_root=aot_root,
            severity_map=severity_map,
            num_workers=num_workers,
            subsample_fraction=subsample_fraction,
            seed=seed,
        )
        # Kill loky workers after each split so their memory is freed before
        # the next split starts (prevents OOM when processing train→val→test).
        get_reusable_executor().shutdown(wait=True)

    logger.info("Done.")


def main(
    aot_root: str,
    bg_class_dir: str,
    output_dir: str,
    corrupted_full_img_dir: str,
    severity_filter: str = "all:1",
    num_workers: int = 8,
    subsample_fraction: float = 1.0,
    splits: str = "train,val,test",
    seed: int = 0,
) -> None:
    """CLI proxy — convert string args and delegate to :func:`create_corrupted`."""
    if isinstance(splits, str):
        split_tuple = tuple(s.strip() for s in splits.split(",") if s.strip())
    else:
        split_tuple = tuple(splits)
    create_corrupted(
        Path(aot_root),
        Path(bg_class_dir),
        Path(output_dir),
        Path(corrupted_full_img_dir),
        severity_filter=severity_filter,
        num_workers=num_workers,
        subsample_fraction=subsample_fraction,
        splits=split_tuple,
        seed=seed,
    )


if __name__ == "__main__":
    fire.Fire(main)
