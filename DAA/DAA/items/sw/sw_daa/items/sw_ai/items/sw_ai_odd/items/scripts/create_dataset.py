"""CLI entry point: build the background-classification dataset.

Seed strategy:
  1. Classify only the FIRST frame of each flight (seed).
  2. Detect imbalance; top-up minority classes with extra frames.
  3. Filter by conf_gate, drop Mix, balance, split, write JSONL.

Usage (via DVC or directly)::

    uv run python scripts/create_dataset.py \\
        --aot_root /path/to/dataset \\
        --output_dir data/01_create_dataset
"""
from __future__ import annotations

import json
import math
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import fire
import torch
from loguru import logger

from src.ood.common.io import write_jsonl
from src.ood.common.path_utils import image_path, parse_frame_path
from src.ood.common.config_loader import load_paths_config
from src.ood.dataset.clip_classifier import (
    CATEGORIES,
    CLASSES,
    PARTS,
    build_clip,
    clip_classify,
    filter_coco_by_frames,
    load_detection_frame_manifest,
    load_groundtruth,
    pick_evenly_skip_first,
    split_by_flight,
    undersample_to_min,
)


def _build_seed_tasks(
    groundtruth: dict[str, dict],
    aot_root: Path,
) -> list[tuple[str, str, str]]:
    """Build one classification task per flight using only the first frame.

    Flights whose first frame is missing from disk are silently skipped.

    Args:
        groundtruth: Dict mapping ``flight_id`` →
            ``{"part": str, "frames": [str, ...]}`` as returned by
            ``load_groundtruth``.
        aot_root: Root path to the AOT dataset.

    Returns:
        List of ``(flight_id, img_name, part)`` tuples, one per flight.
    """
    tasks: list[tuple[str, str, str]] = []
    skipped = 0
    for fid, info in groundtruth.items():
        frames = info["frames"]
        if not frames:
            skipped += 1
            continue
        aot_name = frames[0]  # only the first frame
        part = info["part"]
        if not image_path(fid, aot_name, part, aot_root).exists():
            skipped += 1
            continue
        tasks.append((fid, aot_name, part))
    logger.warning(f"Seed tasks: {len(tasks):,}  (skipped {skipped} missing)")
    return tasks


def _topup(
    records: list[dict],
    groundtruth: dict[str, dict],
    aot_root: Path,
    imbalance_ratio: float,
    conf_gate: float,
    clip_model: torch.nn.Module,
    preprocess: Callable[..., torch.Tensor],
    text_features: torch.Tensor,
    batch_size: int,
    device: str,
) -> list[dict]:
    """Single-pass top-up: classify extra frames to reduce class imbalance.

    Computes the per-class deficit relative to the majority class scaled by
    *imbalance_ratio*, then evenly samples ``ceil(deficit / n_flights)`` extra
    frames from each minority-class flight and classifies them in one batch.

    Args:
        records: Current list of CLIP classification results.
        groundtruth: Full AOT groundtruth dict.
        aot_root: Root path to the AOT dataset.
        imbalance_ratio: A class is considered minority when its count is below
            ``majority / imbalance_ratio``.
        conf_gate: Confidence threshold applied before counting class sizes.
        clip_model: OpenCLIP vision model in eval mode.
        preprocess: OpenCLIP preprocessing transform.
        text_features: Normalised text-feature tensor.
        batch_size: CLIP inference batch size.
        device: PyTorch device string.

    Returns:
        Extended list of records (original + newly classified extra frames).
    """
    usable = [r for r in records if r["label"] in CLASSES and r["confidence"] >= conf_gate]
    counts = Counter(r["label"] for r in usable)
    if not counts:
        return records

    majority = max(counts.values())
    minority_cls = {c for c, n in counts.items() if n < majority / imbalance_ratio}
    if not minority_cls:
        logger.info("No minority classes — skipping top-up.")
        return records

    target = math.ceil(majority / imbalance_ratio)
    logger.info(f"Minority classes: {minority_cls}  target >= {target}  counts: {dict(counts)}")

    # Names already classified — skip them
    seen_names = {r["img_name"] for r in records}

    # Build lookup: real_fid → (fid_key, info)
    fid_lookup: dict[str, tuple[str, dict]] = {}
    for fid, info in groundtruth.items():
        real = fid.split("__")[0]
        if real not in fid_lookup:
            fid_lookup[real] = (fid, info)

    tasks: list[tuple[str, str, str]] = []
    for cls in minority_cls:
        deficit = max(0, target - counts.get(cls, 0))
        if deficit == 0:
            continue
        minority_flight_ids = [r["flight_id"] for r in usable if r["label"] == cls]
        if not minority_flight_ids:
            continue
        # How many extra frames each flight must contribute to cover the whole deficit
        k_per_flight = math.ceil(deficit / len(minority_flight_ids))
        logger.info(
            f"  {cls}: deficit={deficit}, flights={len(minority_flight_ids)}, "
            f"k_per_flight={k_per_flight}"
        )
        for real_fid in minority_flight_ids:
            if real_fid not in fid_lookup:
                continue
            fid_key, info = fid_lookup[real_fid]
            frames = [f for f in info["frames"] if f not in seen_names]
            picked = pick_evenly_skip_first(frames, k_per_flight)
            for fn in picked:
                tasks.append((fid_key, fn, info["part"]))

    if not tasks:
        logger.info("No extra frames available for top-up.")
        return records

    logger.info(f"Classifying {len(tasks):,} extra frames (single pass) …")
    extra = clip_classify(
        tasks,
        clip_model=clip_model,
        preprocess=preprocess,
        text_features=text_features,
        aot_root=aot_root,
        categories=CATEGORIES,
        batch_size=batch_size,
        device=device,
    )
    return records + extra


def _classify_seed_frames(
    aot_root: Path,
    clip_model: str,
    clip_pretrained: str,
    clip_batch: int,
    device: str,
) -> tuple[list[dict], dict[str, dict], torch.nn.Module, Callable[..., torch.Tensor], torch.Tensor]:
    """Load groundtruth, build CLIP, and classify one frame per flight.

    Args:
        aot_root: Root path to the AOT dataset.
        clip_model: OpenCLIP model identifier.
        clip_pretrained: OpenCLIP pretrained weights tag.
        clip_batch: CLIP inference batch size.
        device: PyTorch device string.

    Returns:
        A 5-tuple ``(records, groundtruth, clip_m, preprocess, text_features)``
        where *records* is the initial list of CLIP results (one per flight),
        *groundtruth* is the full AOT groundtruth dict (needed by top-up),
        *clip_m* is the loaded vision model, and *preprocess* / *text_features*
        are the image transform and normalised class embeddings.
    """
    logger.info("Loading AOT groundtruth …")
    groundtruth = load_groundtruth(aot_root, parts=PARTS)

    logger.info(f"Building CLIP [{clip_model} / {clip_pretrained}] …")
    clip_m, preprocess, text_features = build_clip(clip_model, clip_pretrained, device=device)

    seed_tasks = _build_seed_tasks(groundtruth, aot_root)
    logger.info(f"Classifying {len(seed_tasks):,} seed frames (1 per flight) …")
    records = clip_classify(
        seed_tasks,
        clip_model=clip_m,
        preprocess=preprocess,
        text_features=text_features,
        aot_root=aot_root,
        categories=CATEGORIES,
        batch_size=clip_batch,
        device=device,
    )
    logger.info(f"Seed classification done: {len(records):,} records")
    return records, groundtruth, clip_m, preprocess, text_features


def _filter_and_balance(
    records: list[dict],
    *,
    conf_gate: float,
    seed: int,
) -> list[dict]:
    """Deduplicate, filter by confidence, drop the Mix class, and balance.

    Deduplication keeps the last record seen for each ``img_name`` so that
    top-up results override seed results for the same image.

    Args:
        records: Combined seed + top-up CLIP classification results.
        conf_gate: Minimum CLIP confidence to retain a record.
        seed: Random seed for the undersampling step.

    Returns:
        Deduplicated, filtered, and class-balanced record list.
    """
    by_name: dict[str, dict] = {}
    for r in records:
        by_name[r["img_name"]] = r
    records = list(by_name.values())
    logger.info(f"Unique records after dedup: {len(records):,}")

    records = [r for r in records if r["label"] in CLASSES and r["confidence"] >= conf_gate]
    counts = Counter(r["label"] for r in records)
    logger.info(f"After conf_gate + drop Mix: {len(records):,}  {dict(counts)}")

    records = undersample_to_min(records, seed=seed)
    logger.info(f"After balancing: {len(records):,}")
    return records


def _split_and_write(
    records: list[dict],
    output_dir: Path,
    *,
    ratios: tuple[float, float, float],
    seed: int,
) -> None:
    """Split records into flight-disjoint subsets and write one JSONL per split.

    The ``confidence`` field is stripped from each record before writing so
    that downstream stages receive only ``flight_id``, ``img_name``, ``part``,
    and ``label``.

    Args:
        records: Balanced, filtered list of classification records.
        output_dir: Directory where ``train.jsonl``, ``val.jsonl``, and
            ``test.jsonl`` are written (created if it does not exist).
        ratios: ``(train, val, test)`` split fractions; must sum to 1.
        seed: Random seed for reproducibility.
    """
    splits = split_by_flight(records, ratios=ratios, seed=seed)
    for name, recs in splits.items():
        logger.info(f"  {name}: {len(recs):,} records")

    output_dir.mkdir(parents=True, exist_ok=True)
    for name, recs in splits.items():
        clean = [{k: v for k, v in r.items() if k != "confidence"} for r in recs]
        out_path = output_dir / f"{name}.jsonl"
        write_jsonl(out_path, clean)
        logger.info(f"Wrote {out_path}")


def _create_from_detection_frames(
    aot_root: Path,
    input_coco_file: Path,
    output_file: Path,
    crops_output_file: Path,
    *,
    conf_gate: float,
    seed: int,
    clip_m: torch.nn.Module,
    preprocess: Callable[..., torch.Tensor],
    text_features: torch.Tensor,
    clip_batch: int,
    device: str,
) -> None:
    """Classify frames from a COCO JSON file and write the linked outputs.

    Writes two linked artifacts per split:

    * *output_file* — the background-classification JSONL (one record per
      retained full frame: ``img_name``, ``label``, ``path``, ``time``,
      ``flight_id``).
    * *crops_output_file* — a detection COCO JSON filtered to the crops whose
      source frame is retained, preserving crop linkage
      (``source_image_id``, ``crop_x``, ``crop_y``) and detection GT.

    Loads the frame manifest from *input_coco_file*, classifies each frame
    with CLIP, filters by confidence, drops the ``Mix`` class, balances via
    ``undersample_to_min``, and writes the linked outputs.

    Args:
        aot_root: Root path to the AOT dataset on the NAS.
        input_coco_file: Path to a COCO JSON file.
        output_file: Destination background-classification JSONL file path.
        crops_output_file: Destination filtered detection COCO JSON path.
        conf_gate: Minimum CLIP confidence to retain a record.
        seed: Random seed for the undersampling step.
        clip_m: OpenCLIP vision model in eval mode.
        preprocess: OpenCLIP preprocessing transform.
        text_features: Normalised text-feature tensor.
        clip_batch: CLIP inference batch size.
        device: PyTorch device string.
    """
    logger.info(f"Loading frame manifest from {input_coco_file} …")
    frame_paths = load_detection_frame_manifest(input_coco_file)
    logger.info(f"  {len(frame_paths):,} unique frames")

    tasks = [parse_frame_path(p) for p in frame_paths]
    records = clip_classify(
        tasks,
        clip_model=clip_m,
        preprocess=preprocess,
        text_features=text_features,
        aot_root=aot_root,
        categories=CATEGORIES,
        batch_size=clip_batch,
        device=device,
    )
    logger.info(f"  Classified: {len(records):,}")

    records = [
        r for r in records
        if r["label"] in CLASSES and r["confidence"] >= conf_gate
    ]
    logger.info(f"  After conf_gate + drop Mix: {len(records):,}")

    records = undersample_to_min(records, seed=seed)
    logger.info(f"  After balancing: {len(records):,}")

    output_file.parent.mkdir(parents=True, exist_ok=True)
    clean = [{k: v for k, v in r.items() if k != "confidence"} for r in records]
    write_jsonl(output_file, clean)
    logger.info(f"  Wrote {output_file}")

    # Linked crops COCO: keep only crops whose source frame survived balancing.
    retained_frames = {r["path"] for r in records}
    crops_coco = filter_coco_by_frames(input_coco_file, retained_frames)
    crops_output_file.parent.mkdir(parents=True, exist_ok=True)
    with crops_output_file.open("w", encoding="utf-8") as f:
        json.dump(crops_coco, f)
    logger.info(
        f"  Wrote {crops_output_file} "
        f"({len(crops_coco['images']):,} crops / {len(retained_frames):,} frames)"
    )


def create_dataset(
    aot_root: Path,
    output_dir: Path,
    *,
    conf_gate: float,
    imbalance_ratio: float,
    ratios: tuple[float, float, float],
    seed: int,
    clip_model: str,
    clip_pretrained: str,
    clip_batch: int,
    detection_coco_dir: Path | None = None,
    detection_coco_train: str | None = None,
    detection_coco_eval: str | None = None,
    detection_coco_test: str | None = None,
) -> None:
    """Build flight-disjoint train / val / test JSONL splits via CLIP.

    Pipeline:

    1. Load AOT groundtruth and classify **one frame per flight** with CLIP.
    2. Top-up under-represented classes by classifying extra frames from
       minority-class flights (single pass).
    3. Deduplicate, filter by confidence, drop ``"Mix"`` class, and
       undersample to the minority class count.
    4. Create flight-disjoint splits and write JSONL files.

    When *detection_coco_dir* is given, each COCO JSON in that directory
    is processed independently instead of using the seed + top-up flow.

    Args:
        aot_root: Root path to the AOT dataset on the NAS.
        output_dir: Directory where the output JSONL files are written.
        conf_gate: Minimum CLIP confidence to include a record.
        imbalance_ratio: Threshold ratio for triggering minority top-up.
        ratios: ``(train, val, test)`` split fractions; must sum to 1.
        seed: Random seed for reproducibility.
        clip_model: OpenCLIP model identifier.
        clip_pretrained: OpenCLIP pretrained weights tag.
        clip_batch: CLIP inference batch size.
        detection_coco_dir: Optional path to a directory containing
            COCO JSON files to process instead of the seed + top-up flow.
        detection_coco_train: Filename of the train COCO JSON inside
            *detection_coco_dir*.
        detection_coco_eval: Filename of the eval COCO JSON inside
            *detection_coco_dir*.
        detection_coco_test: Filename of the test COCO JSON inside
            *detection_coco_dir*.
    """
    if detection_coco_dir is not None:
        device = "cuda" if torch.cuda.is_available() else "cpu"
        logger.info(f"Using device: {device}")
        logger.info(f"Building CLIP [{clip_model} / {clip_pretrained}] …")
        clip_m, preprocess, text_features = build_clip(clip_model, clip_pretrained, device=device)

        # Detection split name → (COCO filename, OOD output split name)
        split_map = (
            (detection_coco_train, "train"),
            (detection_coco_eval, "val"),
            (detection_coco_test, "test"),
        )
        for coco_filename, ood_split in split_map:
            _create_from_detection_frames(
                aot_root,
                detection_coco_dir / coco_filename,
                output_dir / f"{ood_split}.jsonl",
                output_dir / f"{ood_split}_crops.json",
                conf_gate=conf_gate,
                seed=seed,
                clip_m=clip_m,
                preprocess=preprocess,
                text_features=text_features,
                clip_batch=clip_batch,
                device=device,
            )

        del clip_m
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        return

    device = "cuda" if torch.cuda.is_available() else "cpu"
    logger.info(f"Using device: {device}")

    records, groundtruth, clip_m, preprocess, text_features = _classify_seed_frames(
        aot_root=aot_root,
        clip_model=clip_model,
        clip_pretrained=clip_pretrained,
        clip_batch=clip_batch,
        device=device,
    )
    records = _topup(
        records,
        groundtruth=groundtruth,
        aot_root=aot_root,
        imbalance_ratio=imbalance_ratio,
        conf_gate=conf_gate,
        clip_model=clip_m,
        preprocess=preprocess,
        text_features=text_features,
        batch_size=clip_batch,
        device=device,
    )
    del clip_m
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    records = _filter_and_balance(records, conf_gate=conf_gate, seed=seed)
    _split_and_write(records, output_dir, ratios=ratios, seed=seed)


def main(
    aot_root: str,
    output_dir: str,
    conf_gate: float = 0.80,
    imbalance_ratio: float = 2.0,
    split_ratios: str = "0.70,0.15,0.15",
    seed: int = 0,
    clip_model: str = "ViT-L-14",
    clip_pretrained: str = "laion2b_s32b_b82k",
    clip_batch: int = 32,
    detection_coco_dir: str | None = None,
    detection_coco_train: str | None = None,
    detection_coco_eval: str | None = None,
    detection_coco_test: str | None = None,
) -> None:
    """CLI proxy — parse string args and delegate to :func:`create_dataset`.

    Iteration-specific hyperparameters default to the values used by the
    pipeline; the DVC stage passes them explicitly. Detection COCO paths
    fall back to the constants in dvc_config.yaml when not provided.
    """
    paths_cfg = load_paths_config()

    detection_coco_dir = detection_coco_dir or paths_cfg.get("detection_coco_dir")
    detection_coco_train = detection_coco_train or paths_cfg.get("detection_coco_train")
    detection_coco_eval = detection_coco_eval or paths_cfg.get("detection_coco_eval")
    detection_coco_test = detection_coco_test or paths_cfg.get("detection_coco_test")

    # Handle both str and tuple (Fire may parse comma-separated args as tuples)
    if isinstance(split_ratios, str):
        ratios = tuple(float(r) for r in split_ratios.split(","))
    else:
        ratios = tuple(float(r) for r in split_ratios)
    assert len(ratios) == 3, "split_ratios must have 3 values"
    assert abs(sum(ratios) - 1.0) < 1e-6, "split_ratios must sum to 1"
    create_dataset(
        Path(aot_root),
        Path(output_dir),
        conf_gate=conf_gate,
        imbalance_ratio=imbalance_ratio,
        ratios=ratios,
        seed=seed,
        clip_model=clip_model,
        clip_pretrained=clip_pretrained,
        clip_batch=clip_batch,
        detection_coco_dir=Path(detection_coco_dir) if detection_coco_dir else None,
        detection_coco_train=detection_coco_train,
        detection_coco_eval=detection_coco_eval,
        detection_coco_test=detection_coco_test,
    )


if __name__ == "__main__":
    fire.Fire(main)
