import argparse
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from typing import Any

from loguru import logger
from PIL import Image
from tqdm import tqdm


def _stride(crop: int, overlap: float) -> int:
    """Return the sliding-window stride for a given crop size and overlap ratio.

    Args:
        crop: Crop size in pixels.
        overlap: Overlap fraction between adjacent patches (0–1).

    Returns:
        Stride in pixels (at least 1).
    """
    return max(1, int(crop * (1.0 - overlap)))


def _grid_starts(image_size: int, crop_size: int, stride: int) -> list[int]:
    """Return top-left coordinates for a 1-D sliding window.

    The last window is snapped to end exactly at ``image_size``. If
    ``image_size < crop_size`` a single position at 0 is returned and the
    patch will be zero-padded later.

    Args:
        image_size: Total size along one axis in pixels.
        crop_size: Patch size along that axis.
        stride: Step between consecutive windows.

    Returns:
        Sorted list of start positions.
    """
    if image_size <= crop_size:
        return [0]
    starts: list[int] = []
    s = 0
    while s + crop_size <= image_size:
        starts.append(s)
        s += stride
    last = image_size - crop_size
    if not starts or starts[-1] < last:
        starts.append(last)
    return starts


def _clip_bbox(
    bbox: list[float],
    x0: int,
    y0: int,
    crop_w: int,
    crop_h: int,
    min_visibility: float,
) -> list[float] | None:
    """Clip a COCO bbox to a crop window in crop-local coordinates.

    Args:
        bbox: Source bbox as ``[x, y, w, h]``.
        x0: Crop left edge in source image coordinates.
        y0: Crop top edge in source image coordinates.
        crop_w: Crop width in pixels.
        crop_h: Crop height in pixels.
        min_visibility: Minimum visible-area fraction to keep the bbox.

    Returns:
        Clipped bbox ``[x, y, w, h]`` in crop-local coordinates, or ``None``
        if the visible fraction is below ``min_visibility``.
    """
    bx, by, bw, bh = bbox
    original_area = bw * bh
    if original_area <= 0:
        return None

    ix1 = max(bx, float(x0))
    iy1 = max(by, float(y0))
    ix2 = min(bx + bw, float(x0 + crop_w))
    iy2 = min(by + bh, float(y0 + crop_h))
    if ix2 <= ix1 or iy2 <= iy1:
        return None

    clipped_area = (ix2 - ix1) * (iy2 - iy1)
    if clipped_area / original_area < min_visibility:
        return None
    return [ix1 - x0, iy1 - y0, ix2 - ix1, iy2 - iy1]


def _bbox_intersects_window(
    bbox: list[float],
    x0: int,
    y0: int,
    crop_w: int,
    crop_h: int,
) -> bool:
    """Return True if bbox has any geometric overlap with the crop window.

    Args:
        bbox: Source bbox as ``[x, y, w, h]``.
        x0: Crop left edge.
        y0: Crop top edge.
        crop_w: Crop width.
        crop_h: Crop height.

    Returns:
        True when there is any overlap (no area threshold applied).
    """
    bx, by, bw, bh = bbox
    return not (bx + bw <= x0 or bx >= x0 + crop_w or by + bh <= y0 or by >= y0 + crop_h)


def _save_patch(
    pil_img: Image.Image | None,
    x0: int,
    y0: int,
    crop_w: int,
    crop_h: int,
    file_name: str,
    output_dir: Path,
) -> str:
    """Crop a region from ``pil_img``, zero-pad to ``(crop_w, crop_h)``, and save as PNG.

    Skips writing if the output file already exists (resume support).
    When skipping, ``pil_img`` may be ``None``.

    Args:
        pil_img: Source PIL image (may be ``None`` when the patch already exists).
        x0: Left edge of the crop in source coordinates.
        y0: Top edge of the crop in source coordinates.
        crop_w: Output width in pixels.
        crop_h: Output height in pixels.
        file_name: Source image file name (used to derive the output path).
        output_dir: Root directory for saved patches.

    Returns:
        Workspace-relative path of the saved PNG.
    """
    patch_rel, patch_abs = _patch_path(file_name, x0, y0, output_dir)
    if patch_abs.exists():
        return patch_rel

    assert pil_img is not None
    img_w, img_h = pil_img.size
    actual_w = min(crop_w, img_w - x0)
    actual_h = min(crop_h, img_h - y0)
    patch = pil_img.crop((x0, y0, x0 + actual_w, y0 + actual_h))

    # Pad to exact crop size when the patch is at the image edge
    if actual_w < crop_w or actual_h < crop_h:
        padded = Image.new(pil_img.mode, (crop_w, crop_h), color=0)
        padded.paste(patch, (0, 0))
        patch = padded

    patch_abs.parent.mkdir(parents=True, exist_ok=True)
    patch.save(patch_abs, format="PNG")
    return patch_rel


def _patch_path(file_name: str, x0: int, y0: int, output_dir: Path) -> tuple[str, Path]:
    """Return (relative, absolute) paths for a patch without writing it."""
    stem = Path(file_name).stem
    patch_filename = f"{stem}_x_{x0}_y_{y0}.png"
    patch_rel = str(Path(file_name).parent / patch_filename)
    return patch_rel, output_dir / patch_rel


def _all_patches_exist(
    positions: list[tuple[int, int]] | list[tuple[int, int, list[dict]]],
    file_name: str,
    output_dir: Path,
) -> bool:
    """Return True if every patch file already exists on disk."""
    for pos in positions:
        x0, y0 = pos[0], pos[1]
        _, patch_abs = _patch_path(file_name, x0, y0, output_dir)
        if not patch_abs.exists():
            return False
    return True


def _classify_patches(
    img_anns: list[dict],
    xs: list[int],
    ys: list[int],
    crop_w: int,
    crop_h: int,
    min_visibility: float,
) -> tuple[
    list[tuple[int, int, list[dict]]],
    list[tuple[int, int]],
]:
    """Classify grid positions into annotated and true-background patches.

    A patch is annotated if at least one bbox survives ``min_visibility`` clipping.
    A patch is background only if no source bbox overlaps it at all.
    Patches where bboxes overlap but all fall below ``min_visibility`` are
    discarded (ambiguous partial-object content).

    Args:
        img_anns: Annotations for the source image.
        xs: Candidate x start positions.
        ys: Candidate y start positions.
        crop_w: Crop width in pixels.
        crop_h: Crop height in pixels.
        min_visibility: Minimum visible-area fraction to retain a clipped bbox.

    Returns:
        Tuple of ``(annotated_patches, background_patches)`` where
        ``annotated_patches`` is ``[(x0, y0, [clipped_ann, ...]), ...]`` and
        ``background_patches`` is ``[(x0, y0), ...]``.
    """
    annotated: list[tuple[int, int, list[dict]]] = []
    background: list[tuple[int, int]] = []

    for y0 in ys:
        for x0 in xs:
            has_any_overlap = False
            patch_anns: list[dict] = []

            for ann in img_anns:
                if _bbox_intersects_window(ann["bbox"], x0, y0, crop_w, crop_h):
                    has_any_overlap = True
                    clipped = _clip_bbox(
                        ann["bbox"],
                        x0,
                        y0,
                        crop_w,
                        crop_h,
                        min_visibility,
                    )
                    if clipped is not None:
                        patch_anns.append({**ann, "bbox": clipped})

            if patch_anns:
                # At least one bbox survived clipping → usable foreground
                annotated.append((x0, y0, patch_anns))
            elif not has_any_overlap:
                # No bbox touches this patch at all → true background
                background.append((x0, y0))
            # else: bboxes overlap but all below min_visibility → discard

    return annotated, background


def _get_or_create_video(
    src_video_id: int,
    crop_x: int,
    crop_y: int,
    crop_w: int,
    crop_h: int,
    src_videos: dict[int, dict],
    video_map: dict[tuple[int, int, int], int],
    out_videos: list[dict],
    next_video_id: list[int],
) -> int:
    """Return the output video ID for a ``(source_video, crop_x, crop_y)`` combination.

    Creates a new video record on first encounter.

    Args:
        src_video_id: Source video ID.
        crop_x: Crop left edge in source coordinates.
        crop_y: Crop top edge in source coordinates.
        crop_w: Crop width in pixels.
        crop_h: Crop height in pixels.
        src_videos: Source video records indexed by ID.
        video_map: Cache mapping ``(src_video_id, crop_x, crop_y)`` to output video ID.
        out_videos: Output video list to append new records to.
        next_video_id: Single-element list used as a mutable ID counter.

    Returns:
        Output video ID.
    """
    vkey = (src_video_id, crop_x, crop_y)
    if vkey not in video_map:
        src_v = src_videos.get(src_video_id, {})
        vid = next_video_id[0]
        video_map[vkey] = vid
        out_videos.append(
            {
                **{k: v for k, v in src_v.items() if k not in ("id", "width", "height")},
                "id": vid,
                "width": crop_w,
                "height": crop_h,
                "source_video_id": src_video_id,
                "crop_x": crop_x,
                "crop_y": crop_y,
            }
        )
        next_video_id[0] += 1
    return video_map[vkey]


def _get_or_create_track(
    src_track_id: int,
    new_video_id: int,
    src_tracks: dict[int, dict],
    track_map: dict[tuple[int, int], int],
    out_tracks: list[dict],
    next_track_id: list[int],
) -> int:
    """Return the output track ID for a ``(source_track, output_video)`` combination.

    Creates a new track record on first encounter.

    Args:
        src_track_id: Source track ID.
        new_video_id: Output video ID this track belongs to.
        src_tracks: Source track records indexed by ID.
        track_map: Cache mapping ``(src_track_id, new_video_id)`` to output track ID.
        out_tracks: Output track list to append new records to.
        next_track_id: Single-element list used as a mutable ID counter.

    Returns:
        Output track ID.
    """
    tkey = (src_track_id, new_video_id)
    if tkey not in track_map:
        src_t = src_tracks.get(src_track_id, {})
        tid = next_track_id[0]
        track_map[tkey] = tid
        out_tracks.append(
            {
                **{k: v for k, v in src_t.items() if k not in ("id", "video_id")},
                "id": tid,
                "video_id": new_video_id,
                "source_track_id": src_track_id,
            }
        )
        next_track_id[0] += 1
    return track_map[tkey]


def _build_image_record(
    img_info: dict[str, Any],
    new_id: int,
    patch_rel: str,
    crop_w: int,
    crop_h: int,
    x0: int,
    y0: int,
    video_id: int | None,
) -> dict[str, Any]:
    """Build an output COCO image record for a cropped patch.

    Args:
        img_info: Source image record.
        new_id: ID to assign to the output image.
        patch_rel: Workspace-relative file path of the saved patch.
        crop_w: Patch width in pixels.
        crop_h: Patch height in pixels.
        x0: Crop left edge in source coordinates.
        y0: Crop top edge in source coordinates.
        video_id: Output video ID, or ``None`` if no video association.

    Returns:
        COCO image dict for the patch.
    """
    rec: dict[str, Any] = {
        k: v
        for k, v in img_info.items()
        if k not in ("id", "width", "height", "file_name", "video_id")
    }
    rec.update(
        {
            "id": new_id,
            "width": crop_w,
            "height": crop_h,
            "file_name": patch_rel,
            "source_image_id": img_info["id"],
            "crop_x": x0,
            "crop_y": y0,
        }
    )
    if video_id is not None:
        rec["video_id"] = video_id
    return rec


def _build_annotation_record(
    ann: dict[str, Any],
    new_id: int,
    new_image_id: int,
    track_id: int | None,
) -> dict[str, Any]:
    """Build an output COCO annotation record with crop-local bbox coordinates.

    Args:
        ann: Source annotation with a crop-local bbox already applied.
        new_id: ID to assign to the output annotation.
        new_image_id: ID of the output image this annotation belongs to.
        track_id: Output track ID, or ``None`` if no track association.

    Returns:
        COCO annotation dict.
    """
    bx, by, bw, bh = ann["bbox"]
    rec: dict[str, Any] = {
        k: v
        for k, v in ann.items()
        if k not in ("id", "image_id", "bbox", "area", "segmentation", "track_id")
    }
    rec.update(
        {
            "id": new_id,
            "image_id": new_image_id,
            "bbox": [bx, by, bw, bh],
            "area": bw * bh,
            "segmentation": [],
        }
    )
    if track_id is not None:
        rec["track_id"] = track_id
    return rec


def crop_dataset(
    coco: dict[str, Any],
    images_dir: Path,
    output_dir: Path,
    crop_width: int,
    crop_height: int,
    overlap: float,
    bg_ratio: float,
    min_visibility: float,
    seed: int = 42,
    bg_source: str = "annotated",
) -> dict[str, Any]:
    """Produce a cropped COCO dataset using a sliding-window strategy.

    Each output image is exactly ``(crop_width, crop_height)`` pixels; edge
    patches are zero-padded. One output video is created per unique
    ``(source_video_id, crop_x, crop_y)`` combination so that each output
    video is a temporally coherent spatial sub-region.

    Args:
        coco: Loaded COCO dict with optional ``videos`` and ``tracks`` keys.
        images_dir: Root directory containing source images.
        output_dir: Directory where patch images will be saved.
        crop_width: Patch width in pixels.
        crop_height: Patch height in pixels.
        overlap: Fraction of overlap between adjacent patches (0–1).
        bg_ratio: Background-patch fraction relative to annotated patches per image.
        min_visibility: Minimum visible-area fraction to retain a clipped bbox.
        seed: Random seed for background sampling.
        bg_source: Where to draw background patches from.  ``"annotated"``
            (default) generates background patches only from images that have
            at least one annotation.  ``"all"`` also generates background
            patches from completely unannotated images (using ``bg_ratio``
            relative to the total grid positions).

    Returns:
        COCO dict for the cropped dataset.
    """
    rng = random.Random(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    # ---- Source lookups ----
    anns_by_image: dict[int, list[dict]] = defaultdict(list)
    for ann in coco.get("annotations", []):
        anns_by_image[ann["image_id"]].append(ann)

    src_videos: dict[int, dict] = {v["id"]: v for v in coco.get("videos", [])}
    src_tracks: dict[int, dict] = {t["id"]: t for t in coco.get("tracks", [])}

    # ---- Output containers ----
    out_images: list[dict] = []
    out_annotations: list[dict] = []
    out_videos: list[dict] = []
    out_tracks: list[dict] = []
    new_image_id = 1
    new_ann_id = 1

    # Mutable counters (single-element lists) and lookup maps
    next_video_id = [1]
    next_track_id = [1]
    video_map: dict[tuple[int, int, int], int] = {}
    track_map: dict[tuple[int, int], int] = {}

    stride_x = _stride(crop_width, overlap)
    stride_y = _stride(crop_height, overlap)

    for img_info in tqdm(coco["images"], desc="Cropping images", unit="img"):
        img_id = img_info["id"]
        img_w = img_info["width"]
        img_h = img_info["height"]
        file_name: str = img_info["file_name"]
        src_video_id: int | None = img_info.get("video_id")

        img_path = images_dir / file_name
        if not img_path.exists():
            logger.warning(f"Image not found, skipping: {img_path}")
            continue

        img_anns = anns_by_image.get(img_id, [])

        xs = _grid_starts(img_w, crop_width, stride_x)
        ys = _grid_starts(img_h, crop_height, stride_y)

        annotated_patches, background_patches = _classify_patches(
            img_anns,
            xs,
            ys,
            crop_width,
            crop_height,
            min_visibility,
        )

        # Sample a controlled number of true-background patches
        if annotated_patches:
            n_bg = max(0, math.ceil(len(annotated_patches) * bg_ratio))
        elif bg_source == "all":
            n_bg = max(0, math.ceil(len(background_patches) * bg_ratio))
        else:
            n_bg = 0
        sampled_bg = rng.sample(
            background_patches,
            min(n_bg, len(background_patches)),
        )

        # Skip opening the source image if all patches already exist
        all_exist = _all_patches_exist(
            annotated_patches, file_name, output_dir
        ) and _all_patches_exist(sampled_bg, file_name, output_dir)

        pil_img: Image.Image | None = None
        if not all_exist:
            pil_img = Image.open(img_path)

        # ---- Annotated patches ----
        for x0, y0, patch_anns in annotated_patches:
            patch_rel = _save_patch(
                pil_img,
                x0,
                y0,
                crop_width,
                crop_height,
                file_name,
                output_dir,
            )

            video_id: int | None = None
            if src_video_id is not None:
                video_id = _get_or_create_video(
                    src_video_id,
                    x0,
                    y0,
                    crop_width,
                    crop_height,
                    src_videos,
                    video_map,
                    out_videos,
                    next_video_id,
                )

            out_images.append(
                _build_image_record(
                    img_info,
                    new_image_id,
                    patch_rel,
                    crop_width,
                    crop_height,
                    x0,
                    y0,
                    video_id,
                )
            )

            for ann in patch_anns:
                track_id: int | None = None
                src_tid = ann.get("track_id")
                if src_tid is not None and video_id is not None:
                    track_id = _get_or_create_track(
                        src_tid,
                        video_id,
                        src_tracks,
                        track_map,
                        out_tracks,
                        next_track_id,
                    )

                out_annotations.append(
                    _build_annotation_record(
                        ann,
                        new_ann_id,
                        new_image_id,
                        track_id,
                    )
                )
                new_ann_id += 1

            new_image_id += 1

        # ---- True-background patches ----
        for x0, y0 in sampled_bg:
            patch_rel = _save_patch(
                pil_img,
                x0,
                y0,
                crop_width,
                crop_height,
                file_name,
                output_dir,
            )

            video_id = None
            if src_video_id is not None:
                video_id = _get_or_create_video(
                    src_video_id,
                    x0,
                    y0,
                    crop_width,
                    crop_height,
                    src_videos,
                    video_map,
                    out_videos,
                    next_video_id,
                )

            out_images.append(
                _build_image_record(
                    img_info,
                    new_image_id,
                    patch_rel,
                    crop_width,
                    crop_height,
                    x0,
                    y0,
                    video_id,
                )
            )
            new_image_id += 1

        if pil_img is not None:
            pil_img.close()

    # ---- Assemble output COCO dict ----
    out_coco: dict[str, Any] = {
        k: v for k, v in coco.items() if k not in ("images", "annotations", "videos", "tracks")
    }
    out_coco["images"] = out_images
    out_coco["annotations"] = out_annotations
    if out_videos:
        out_coco["videos"] = out_videos
    if out_tracks:
        out_coco["tracks"] = out_tracks
    return out_coco


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Sliding-window crop of a COCO dataset to a target resolution.",
    )
    p.add_argument("--input-json", required=True, help="Path to input COCO JSON.")
    p.add_argument("--images-dir", required=True, help="Root directory of source images.")
    p.add_argument("--output-json", required=True, help="Path for the output COCO JSON.")
    p.add_argument("--output-dir", required=True, help="Directory to save cropped images.")
    p.add_argument("--crop-width", type=int, default=640)
    p.add_argument("--crop-height", type=int, default=640)
    p.add_argument(
        "--overlap",
        type=float,
        default=0.2,
        help="Overlap fraction between adjacent patches [0, 1). Default: 0.2",
    )
    p.add_argument(
        "--bg-ratio",
        type=float,
        default=0.1,
        help="Background-patch ratio relative to annotated patches. Default: 0.1",
    )
    p.add_argument(
        "--min-visibility",
        type=float,
        default=0.3,
        help="Min visible area fraction to retain a clipped bbox. Default: 0.3",
    )
    p.add_argument("--seed", type=int, default=42)
    p.add_argument(
        "--bg-source",
        choices=["annotated", "all"],
        default="annotated",
        help=(
            "Where to draw background patches from. "
            "'annotated' (default) only from images with annotations. "
            "'all' also from completely unannotated images."
        ),
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    with open(args.input_json) as f:
        coco = json.load(f)

    logger.info(
        f"Loaded {len(coco['images'])} images, "
        f"{len(coco.get('annotations', []))} annotations, "
        f"{len(coco.get('videos', []))} videos, "
        f"{len(coco.get('tracks', []))} tracks"
    )

    out_coco = crop_dataset(
        coco=coco,
        images_dir=Path(args.images_dir),
        output_dir=Path(args.output_dir),
        crop_width=args.crop_width,
        crop_height=args.crop_height,
        overlap=args.overlap,
        bg_ratio=args.bg_ratio,
        min_visibility=args.min_visibility,
        seed=args.seed,
        bg_source=args.bg_source,
    )

    out_path = Path(args.output_json)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump(out_coco, f)

    logger.info(
        f"Done — {len(out_coco['images'])} patches, "
        f"{len(out_coco['annotations'])} annotations, "
        f"{len(out_coco.get('videos', []))} videos, "
        f"{len(out_coco.get('tracks', []))} tracks "
        f"-> {args.output_json}"
    )


if __name__ == "__main__":
    main()
