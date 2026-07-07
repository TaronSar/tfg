"""CLIP-based background classification for AOT dataset frames."""
from __future__ import annotations

import json
import random
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import yaml
from PIL import Image
from tqdm.auto import tqdm

from src.ood.common.path_utils import (
    crop_to_frame_path,
    image_path,
    relative_path,
)

# ── AOT dataset constants ─────────────────────────────────────────────────────
PARTS = ("part1", "part2", "part3")

_CONFIG_PATH = Path(__file__).parent.parent.parent.parent / "configs" / "dvc_config.yaml"


def _load_clip_config() -> tuple[list[str], str, dict[str, list[str]]]:
    """Load CLIP taxonomy from ``configs/dvc_config.yaml``.

    Returns:
        A 3-tuple ``(categories, mix_category, prompts)`` where *categories*
        is the full list including the mix class, *mix_category* is the name
        of the class to discard after classification, and *prompts* maps each
        category name to its list of text prompts.
    """
    with _CONFIG_PATH.open() as _f:
        cfg = yaml.safe_load(_f)["dataset"]
    classes: list[str] = cfg["classes"]
    mix_category: str = cfg["mix_category"]
    categories: list[str] = classes + [mix_category]
    prompts: dict[str, list[str]] = cfg["prompts"]
    return categories, mix_category, prompts


# 4-class CLIP taxonomy — loaded from dvc_config.yaml
CATEGORIES, MIX_CATEGORY, PROMPTS = _load_clip_config()
CLASSES = [c for c in CATEGORIES if c != MIX_CATEGORY]  # valid output classes


# ── AOT filename helpers ──────────────────────────────────────────────────────
def img_name_to_timestamp(img_name: str, flight_id: str) -> str:
    """Extract the 19-digit nanosecond timestamp from an AOT image name.

    AOT image names follow the pattern ``<19-digit-ns-timestamp><flight_id>.png``.

    Args:
        img_name: AOT image filename (with or without ``.png`` extension).
        flight_id: Flight identifier appended after the timestamp.

    Returns:
        The 19-digit timestamp string.
    """
    stem = img_name[:-4] if img_name.endswith(".png") else img_name
    if stem.endswith(flight_id):
        stem = stem[: -len(flight_id)]
    return stem


def collect_frames(seq_data: dict) -> list[str]:
    """Return all frame names known for a sequence (sorted chronologically).

    Looks for frame names in ``entities``, ``image_names``, and ``frames``
    keys of the sequence dictionary.

    Args:
        seq_data: Raw sequence dictionary loaded from AOT groundtruth JSON.

    Returns:
        Sorted list of unique frame filename strings.
    """
    names: set[str] = set()
    for ent in seq_data.get("entities", []):
        n = ent.get("img_name")
        if n:
            names.add(n)
    for key in ("image_names", "frames"):
        for n in seq_data.get(key, []) or []:
            if n:
                names.add(n)
    return sorted(names)


# ── Detection COCO helpers ────────────────────────────────────────────────────


def load_detection_frame_manifest(coco_file: Path) -> list[str]:
    """Read a detection COCO JSON and return unique original frame paths.

    Args:
        coco_file: Path to a single detection COCO JSON file.

    Returns:
        Sorted list of unique AOT-relative frame paths recovered from the
        crop ``file_name`` entries in the COCO file.
    """
    with open(coco_file, encoding="utf-8") as f:
        coco = json.load(f)
    frames: set[str] = set()
    for img in coco["images"]:
        frames.add(crop_to_frame_path(img["file_name"]))
    return sorted(frames)


def filter_coco_by_frames(coco_file: Path, retained_frames: set[str]) -> dict:
    """Filter a detection COCO JSON to crops whose source frame is retained.

    Keeps every image whose original (uncropped) frame path is in
    *retained_frames* and the annotations that reference those images.  All
    non image/annotation top-level keys (``info``, ``licenses``,
    ``categories``, ``videos`` …) are preserved verbatim so the crop linkage
    fields (``source_image_id``, ``crop_x``, ``crop_y``) and detection GT
    survive unchanged.

    Args:
        coco_file: Path to the source detection COCO JSON.
        retained_frames: Set of AOT-relative original frame paths to keep
            (as produced by :func:`crop_to_frame_path`).

    Returns:
        A new COCO dict containing only the retained images and their
        annotations.
    """
    with open(coco_file, encoding="utf-8") as f:
        coco = json.load(f)

    kept_images = [
        img for img in coco["images"]
        if crop_to_frame_path(img["file_name"]) in retained_frames
    ]
    kept_image_ids = {img["id"] for img in kept_images}
    kept_annotations = [
        ann for ann in coco.get("annotations", [])
        if ann["image_id"] in kept_image_ids
    ]

    out = {k: v for k, v in coco.items() if k not in ("images", "annotations")}
    out["images"] = kept_images
    out["annotations"] = kept_annotations
    return out


# ── Groundtruth loading ───────────────────────────────────────────────────────
def load_groundtruth(
    aot_root: Path,
    parts: tuple[str, ...] = PARTS,
) -> dict[str, dict]:
    """Load and merge groundtruth JSON from all dataset parts.

    Collision-resolves duplicate flight IDs across parts by appending
    ``"__<part>"`` to the key.

    Args:
        aot_root: Root path to the AOT dataset.
        parts: Tuple of part identifiers to process (default: all three parts).

    Returns:
        Dict mapping ``flight_id`` → ``{"part": str, "frames": [str, ...]}``.  
    """
    groundtruth: dict[str, dict] = {}
    collisions = 0
    for part in parts:
        gt_path = aot_root / part / "ImageSets" / "groundtruth.json"
        with open(gt_path, encoding="utf-8") as f:
            samples = json.load(f).get("samples", {})
        print(f"[{part}] {len(samples)} sequences")
        for fid, seq in samples.items():
            if fid in groundtruth:
                collisions += 1
                fid_unique = f"{fid}__{part}"
            else:
                fid_unique = fid
            groundtruth[fid_unique] = {
                "part": part,
                "frames": collect_frames(seq),
            }
        del samples
    print(f"Total flights: {len(groundtruth)} (collisions: {collisions})")
    return groundtruth


# ── CLIP helpers ──────────────────────────────────────────────────────────────
def build_clip(
    model_name: str,
    pretrained: str,
    device: str,
    categories: list[str] = CATEGORIES,
    prompts: dict[str, list[str]] = PROMPTS,
) -> tuple:
    """Build and return a CLIP model ready for zero-shot classification.

    Args:
        model_name: OpenCLIP model identifier (e.g. ``"ViT-L-14"``).
        pretrained: OpenCLIP pretrained weights tag (e.g.
            ``"laion2b_s32b_b82k"``).
        device: PyTorch device string.
        categories: List of class name strings used to build text features.
        prompts: Dict mapping each category name to a list of prompt strings.

    Returns:
        A 3-tuple ``(model, preprocess, text_features)`` where *text_features*
        is a ``(len(categories), D)`` normalised tensor of mean prompt
        embeddings.
    """
    import open_clip

    model, _, preprocess = open_clip.create_model_and_transforms(
        model_name, pretrained=pretrained
    )
    tokenizer = open_clip.get_tokenizer(model_name)
    model = model.to(device).eval()
    with torch.no_grad():
        class_vecs = []
        for cat in categories:
            tok = tokenizer(prompts[cat]).to(device)
            f = model.encode_text(tok)
            f = f / f.norm(dim=-1, keepdim=True)
            m = f.mean(dim=0)
            m = m / m.norm()
            class_vecs.append(m)
        text_features = torch.stack(class_vecs, dim=0)
    return model, preprocess, text_features


def clip_classify(
    tasks: list[tuple[str, str, str]],
    clip_model,
    preprocess,
    text_features: torch.Tensor,
    aot_root: Path,
    categories: list[str] = CATEGORIES,
    batch_size: int = 32,
    device: str = "cpu",
) -> list[dict]:
    """Classify a list of ``(flight_id, img_name, part)`` tuples with CLIP.

    Args:
        tasks: List of ``(flight_id, img_name, part)`` tuples to classify.
        clip_model: OpenCLIP vision model in eval mode.
        preprocess: OpenCLIP preprocessing transform.
        text_features: Normalised text-feature tensor of shape
            ``(len(categories), D)``.
        aot_root: Root path to the AOT dataset.
        categories: List of category name strings matching *text_features* rows.
        batch_size: Number of images per inference batch.
        device: PyTorch device string.

    Returns:
        List of dicts (one per successfully classified image) with fields
        ``img_name``, ``label``, ``confidence``, ``path``, ``time``, and
        ``flight_id``.  Images that do not exist on disk are silently skipped.
    """
    results: list[dict] = []
    with torch.no_grad():
        for i in tqdm(range(0, len(tasks), batch_size), desc="CLIP", unit="batch"):
            chunk = tasks[i : i + batch_size]
            imgs: list[torch.Tensor] = []
            ok: list[tuple[str, str, str]] = []
            for fid, aot_name, part in chunk:
                p = image_path(fid, aot_name, part, aot_root)
                if not p.exists():
                    continue
                try:
                    img = Image.open(p).convert("RGB")
                    w, h = img.size
                    cropped = img.crop((0, h // 2, w, h))
                    imgs.append(preprocess(cropped))
                    ok.append((fid, aot_name, part))
                except Exception:
                    continue
            if not imgs:
                continue
            batch = torch.stack(imgs).to(device)
            feats = clip_model.encode_image(batch)
            feats = feats / feats.norm(dim=-1, keepdim=True)
            logits = (feats @ text_features.T) * 100.0
            probs = logits.softmax(dim=-1).cpu().numpy()
            for (fid, aot_name, part), p_vec in zip(ok, probs, strict=False):
                label_idx = int(np.argmax(p_vec))
                label = categories[label_idx]
                confidence = float(p_vec[label_idx])
                results.append({
                    "img_name": aot_name,
                    "label": label,
                    "confidence": confidence,
                    "path": relative_path(fid, aot_name, part),
                    "time": img_name_to_timestamp(aot_name, fid.split("__")[0]),
                    "flight_id": fid.split("__")[0],
                })
    return results


# ── Imbalance top-up ──────────────────────────────────────────────────────────
def pick_evenly_skip_first(frames: list[str], k: int) -> list[str]:
    """Pick *k* frames evenly spaced across *frames*, excluding index 0.

    Args:
        frames: Ordered list of frame filenames.
        k: Number of frames to pick.

    Returns:
        List of up to *k* frame filenames selected at evenly spaced indices
        (index 0 is always excluded).
    """
    if len(frames) <= 1:
        return []
    idx = np.linspace(0, len(frames) - 1, k + 1).round().astype(int)
    idx = sorted(set(idx.tolist()) - {0})
    if len(idx) > k:
        idx = idx[:k]
    return [frames[i] for i in idx]


# ── Balancing & splitting ─────────────────────────────────────────────────────
def undersample_to_min(records: list[dict], seed: int = 0) -> list[dict]:
    """Deterministically undersample each class to the minority class count.

    Args:
        records: List of classification records, each with a ``"label"`` field.
        seed: Random seed for reproducibility.

    Returns:
        Balanced list of records where every class has exactly ``min_count``
        entries (where ``min_count`` is the smallest per-class count).
    """
    by_class: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        by_class[rec["label"]].append(i)
    n_min = min(len(v) for v in by_class.values())
    rng = random.Random(seed)
    keep: list[int] = []
    for _cls, idxs in by_class.items():
        rng.shuffle(idxs)
        keep.extend(idxs[:n_min])
    keep.sort()
    return [records[i] for i in keep]


def split_by_flight(
    records: list[dict],
    ratios: tuple[float, float, float] = (0.70, 0.15, 0.15),
    seed: int = 0,
) -> dict[str, list[dict]]:
    """Create flight-disjoint train / val / test splits.

    Each flight's records land entirely in one split to prevent data leakage.
    Flights are assigned greedily until each split reaches its target record
    count.

    Args:
        records: Balanced list of classification records.  Each record must
            have a ``"flight_id"`` field.
        ratios: 3-tuple of ``(train, val, test)`` fractions summing to 1.
        seed: Random seed for flight-order shuffling.

    Returns:
        Dict ``{"train": [...], "val": [...], "test": [...]}``.  Records are
        in original order within each split.
    """
    by_flight: dict[str, list[int]] = defaultdict(list)
    for i, rec in enumerate(records):
        by_flight[rec["flight_id"]].append(i)
    flights = list(by_flight.keys())
    rng = random.Random(seed)
    rng.shuffle(flights)

    n_total = len(records)
    target_train = int(round(ratios[0] * n_total))
    target_val = int(round(ratios[1] * n_total))

    splits: dict[str, list[int]] = {"train": [], "val": [], "test": []}
    for fid in flights:
        size = len(by_flight[fid])
        if len(splits["train"]) + size <= target_train:
            splits["train"].extend(by_flight[fid])
        elif len(splits["val"]) + size <= target_val:
            splits["val"].extend(by_flight[fid])
        else:
            splits["test"].extend(by_flight[fid])

    return {k: [records[i] for i in idxs] for k, idxs in splits.items()}
