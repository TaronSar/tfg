"""CLI entry point: crop persisted corrupted full frames at the detection offsets.

Stage 06 of the OOD pipeline.  Consumes:

* the corrupted full-size frames written by ``create_corrupted.py``
  (stage 05), indexed by the local per-split ``dataset.jsonl`` manifests, and
* the curated detection crops COCO JSONs produced by ``apply_curation.py``
  (stage 04, ``<split>_crops.json``), which carry the crop offsets and the
  detection ground-truth annotations.

For each corrupted full frame it extracts the same crop regions used by the
detection pipeline (``crop_x``/``crop_y``, ``crop_size``×``crop_size``) and
writes the resulting crops in an AOT-mirrored, split-independent
layout::

    <corrupted_crops_img_dir>/<part>/Images/<flight>/<frame_stem>_x_<X>_y_<Y>_<type>_<sev>.png

A local corrupted-crops COCO JSON is emitted per split
(``<output_dir>/<split>_crops.json``) whose ``file_name`` fields are relative
to *corrupted_crops_img_dir* and whose annotations are inherited (crop-local) from the
clean detection crops.  Clean crops are NOT regenerated — the detection
``airborne_cropped_images/`` tree is reused directly by the inference stage.

Usage (via DVC or directly)::

    uv run python scripts/create_corrupted_crops.py \\
        --corrupted_full_dir data/05_create_corrupted_full \\
        --crops_coco_dir data/04_apply_curation \\
        --corrupted_full_img_dir /mnt/Pool_IA/IA_Dataset/datasets/airborne_corrupted_images/full \\
        --corrupted_crops_img_dir /mnt/Pool_IA/IA_Dataset/datasets/airborne_corrupted_images/cropped \\
        --output_dir data/06_create_corrupted_crops \\
        --crop_size 960 \\
        --num_workers 8
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import fire
import numpy as np
from joblib import Parallel, delayed
from joblib.externals.loky import get_reusable_executor
from loguru import logger
from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

from src.ood.common.coco_utils import crop_offset_from_entry
from src.ood.common.io import read_jsonl
from src.ood.common.path_utils import crop_to_frame_path
from src.ood.preprocessing.corruptions import _is_valid_image, _worker_init, corrupted_crop_rel, corrupted_full_path


def _process_corrupted_full(
    rec: dict,
    crops: list[dict],
    corrupted_full_img_dir: Path,
    corrupted_crops_img_dir: Path,
    crop_size: int,
) -> list[dict]:
    """Crop one corrupted full frame at every detection offset for that frame.

    Args:
        rec: Corrupted-full manifest record with fields ``path`` (AOT-relative
            source frame), ``type``, and ``severity``.
        crops: COCO image entries whose source frame matches ``rec["path"]``.
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        corrupted_crops_img_dir: Root of the corrupted crops tree.
        crop_size: Square crop side length in pixels (e.g. 960).

    Returns:
        List of partial COCO image entries (one per crop) with fields
        ``orig_crop_id``, ``file_name`` (storage-relative corrupted crop path),
        ``width``, ``height``, ``crop_x``, ``crop_y``, ``source_frame``,
        ``corruption_type``, and ``corruption_severity``.  Returns an empty
        list if the corrupted full frame is missing from storage.
    """
    ctype = rec["type"]
    sev = int(rec["severity"])
    out_entries: list[dict] = []
    to_generate: list[tuple[dict, int, int, int, int, str, Path]] = []
    for crop in crops:
        x0, y0 = crop_offset_from_entry(crop)
        cw = int(crop.get("width", crop_size))
        ch = int(crop.get("height", crop_size))

        corr_rel = corrupted_crop_rel(crop["file_name"], ctype, sev)
        out_abs = corrupted_crops_img_dir / corr_rel

        if _is_valid_image(out_abs):
            out_entries.append(
                {
                    "orig_crop_id": int(crop["id"]),
                    "file_name": corr_rel,
                    "width": cw,
                    "height": ch,
                    "crop_x": x0,
                    "crop_y": y0,
                    "source_frame": rec["path"],
                    "corruption_type": ctype,
                    "corruption_severity": sev,
                }
            )
            continue

        if out_abs.exists():
            logger.warning(f"Invalid existing corrupted crop found, regenerating: {out_abs}")
            try:
                out_abs.unlink(missing_ok=True)
            except OSError:
                pass
        to_generate.append((crop, x0, y0, cw, ch, corr_rel, out_abs))

    # All crops already exist and are readable; avoid loading the full image.
    if not to_generate:
        return out_entries

    full_path = corrupted_full_path(rec["path"], ctype, sev, corrupted_full_img_dir)
    if not full_path.exists():
        logger.warning(f"Corrupted full frame missing: {full_path}")
        return out_entries

    try:
        full_img = np.array(Image.open(full_path).convert("RGB"), dtype=np.uint8)
    except (OSError, UnidentifiedImageError) as exc:
        logger.warning(
            f"Skipping unreadable corrupted full frame: {full_path} ({exc})"
        )
        return out_entries
    img_h, img_w = full_img.shape[:2]

    for crop, x0, y0, cw, ch, corr_rel, out_abs in to_generate:

        actual_w = min(cw, img_w - x0)
        actual_h = min(ch, img_h - y0)
        patch = full_img[y0 : y0 + actual_h, x0 : x0 + actual_w]
        if actual_w < cw or actual_h < ch:
            padded = np.zeros((ch, cw, 3), dtype=np.uint8)
            padded[:actual_h, :actual_w] = patch
            patch = padded
        out_abs.parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(patch).save(out_abs)
        if not _is_valid_image(out_abs):
            logger.warning(f"Failed to generate a valid corrupted crop: {out_abs}")
            try:
                out_abs.unlink(missing_ok=True)
            except OSError:
                pass
            continue

        out_entries.append(
            {
                "orig_crop_id": int(crop["id"]),
                "file_name": corr_rel,
                "width": cw,
                "height": ch,
                "crop_x": x0,
                "crop_y": y0,
                "source_frame": rec["path"],
                "corruption_type": ctype,
                "corruption_severity": sev,
            }
        )
    return out_entries


def _build_corrupted_coco(
    partial_entries: list[dict],
    clean_coco: dict,
) -> dict:
    """Assemble a corrupted-crops COCO dict from worker partial entries.

    Assigns fresh, globally-unique image and annotation IDs and copies the
    crop-local ground-truth annotations from the clean detection COCO.

    Args:
        partial_entries: Flattened output of :func:`_process_corrupted_full`.
        clean_coco: The clean detection crops COCO dict (source of annotations
            and categories).

    Returns:
        A COCO dict with ``images``, ``annotations``, and ``categories`` keys.
    """
    anns_by_crop: dict[int, list[dict]] = defaultdict(list)
    for ann in clean_coco.get("annotations", []):
        anns_by_crop[int(ann["image_id"])].append(ann)

    images: list[dict] = []
    annotations: list[dict] = []
    img_id = 1
    ann_id = 1
    for entry in partial_entries:
        orig_crop_id = entry.pop("orig_crop_id")
        new_entry = {"id": img_id, **entry}
        images.append(new_entry)
        for ann in anns_by_crop.get(orig_crop_id, []):
            annotations.append({**ann, "id": ann_id, "image_id": img_id})
            ann_id += 1
        img_id += 1

    return {
        "images": images,
        "annotations": annotations,
        "categories": clean_coco.get("categories", []),
    }


def _process_split(
    split_name: str,
    corrupted_full_dir: Path,
    crops_coco_dir: Path,
    corrupted_full_img_dir: Path,
    corrupted_crops_img_dir: Path,
    output_dir: Path,
    crop_size: int,
    num_workers: int,
) -> None:
    """Generate corrupted crops + COCO JSON for one split.

    Args:
        split_name: One of ``"train"``, ``"val"``, ``"test"``.
        corrupted_full_dir: Root local dir holding ``<split>/dataset.jsonl``.
        crops_coco_dir: Dir holding the curated ``<split>_crops.json``.
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        corrupted_crops_img_dir: Root of the corrupted crops tree.
        output_dir: Local output dir for the corrupted-crops COCO JSON.
        crop_size: Square crop side length in pixels.
        num_workers: Number of parallel joblib workers.
    """
    manifest = corrupted_full_dir / split_name / "dataset.jsonl"
    crops_json = crops_coco_dir / f"{split_name}_crops.json"
    if not manifest.exists():
        logger.warning(f"  {manifest} not found — skipping {split_name}")
        return
    if not crops_json.exists():
        logger.warning(f"  {crops_json} not found — skipping {split_name}")
        return

    records = read_jsonl(manifest)
    with open(crops_json, encoding="utf-8") as f:
        clean_coco = json.load(f)

    # Group clean crop entries by their parent full frame.
    crops_by_frame: dict[str, list[dict]] = defaultdict(list)
    for img in clean_coco["images"]:
        crops_by_frame[crop_to_frame_path(img["file_name"])].append(img)

    # Keep only corrupted-full records whose frame has crops to extract.
    jobs_args = [
        (rec, crops_by_frame[rec["path"]])
        for rec in records
        if rec["path"] in crops_by_frame
    ]
    logger.info(
        f"  [{split_name}] {len(jobs_args):,} corrupted frames × crops "
        f"(from {len(records):,} manifest records)"
    )
    if not jobs_args:
        return

    jobs = (
        delayed(_process_corrupted_full)(
            rec=rec,
            crops=crops,
            corrupted_full_img_dir=corrupted_full_img_dir,
            corrupted_crops_img_dir=corrupted_crops_img_dir,
            crop_size=crop_size,
        )
        for rec, crops in jobs_args
    )
    parallel = Parallel(
        n_jobs=num_workers,
        backend="loky",
        initializer=_worker_init,
        return_as="generator_unordered",
    )
    results = list(
        tqdm(parallel(jobs), total=len(jobs_args), desc=split_name, unit="frame")
    )

    partial_entries = [e for batch in results if batch for e in batch]
    coco = _build_corrupted_coco(partial_entries, clean_coco)

    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / f"{split_name}_crops.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(coco, f)
    logger.info(
        f"  [{split_name}] {len(coco['images']):,} corrupted crops, "
        f"{len(coco['annotations']):,} annotations → {out_path}"
    )


def create_corrupted_crops(
    corrupted_full_dir: Path,
    crops_coco_dir: Path,
    corrupted_full_img_dir: Path,
    corrupted_crops_img_dir: Path,
    output_dir: Path,
    *,
    crop_size: int = 960,
    num_workers: int = 8,
    splits: tuple[str, ...] = ("train", "val", "test"),
) -> None:
    """Crop persisted corrupted full frames at the detection crop offsets.

    Args:
        corrupted_full_dir: Root local dir holding ``<split>/dataset.jsonl``
            manifests produced by stage 05.
        crops_coco_dir: Dir holding the curated ``<split>_crops.json`` files
            produced by stage 04.
        corrupted_full_img_dir: Root of the corrupted full-image tree.
        corrupted_crops_img_dir: Root of the corrupted crops tree.
        output_dir: Local output dir for the corrupted-crops COCO JSONs.
        crop_size: Square crop side length in pixels (default 960).
        num_workers: Number of parallel joblib workers.
        splits: Which splits to process.
    """
    logger.info(f"Corrupted crops root: {corrupted_crops_img_dir}")
    logger.info(f"Crop size: {crop_size}  |  workers: {num_workers}  |  splits: {splits}")
    corrupted_crops_img_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    for split_name in splits:
        _process_split(
            split_name=split_name,
            corrupted_full_dir=corrupted_full_dir,
            crops_coco_dir=crops_coco_dir,
            corrupted_full_img_dir=corrupted_full_img_dir,
            corrupted_crops_img_dir=corrupted_crops_img_dir,
            output_dir=output_dir,
            crop_size=crop_size,
            num_workers=num_workers,
        )
        get_reusable_executor().shutdown(wait=True)

    logger.info("Done.")


def main(
    corrupted_full_dir: str,
    crops_coco_dir: str,
    corrupted_full_img_dir: str,
    corrupted_crops_img_dir: str,
    output_dir: str,
    crop_size: int = 960,
    num_workers: int = 8,
    splits: str = "train,val,test",
) -> None:
    """CLI proxy — convert string args and delegate to :func:`create_corrupted_crops`."""
    if isinstance(splits, str):
        split_tuple = tuple(s.strip() for s in splits.split(",") if s.strip())
    else:
        split_tuple = tuple(splits)
    create_corrupted_crops(
        Path(corrupted_full_dir),
        Path(crops_coco_dir),
        Path(corrupted_full_img_dir),
        Path(corrupted_crops_img_dir),
        Path(output_dir),
        crop_size=crop_size,
        num_workers=num_workers,
        splits=split_tuple,
    )


if __name__ == "__main__":
    fire.Fire(main)
