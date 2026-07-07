import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import cv2
from loguru import logger
from tqdm import tqdm


def _resolve_image_path(base_dir: str, stored_filename: str) -> Path:
    """Resolve an image file path from a COCO filename and a user-supplied base directory.

    Tries several resolution strategies in order:
    absolute path, relative to base, relative to base stripping leading slash.

    Args:
        base_dir: Root directory used as a fallback for relative filenames.
        stored_filename: Image filename as stored in the COCO annotation.

    Returns:
        Path: Resolved, existing path to the image file.

    Raises:
        FileNotFoundError: If no resolution strategy locates the file.
    """
    p = Path(stored_filename)
    base_path = Path(base_dir)

    if p.is_absolute() and p.exists():
        return p

    candidate = base_path / stored_filename
    if candidate.exists():
        return candidate

    candidate = base_path / stored_filename.lstrip("/")
    if candidate.exists():
        return candidate

    raise FileNotFoundError(
        f"Cannot resolve image path for {stored_filename} with base {base_path}"
    )


def _build_indexes(
    coco_annotation: dict[str, Any],
) -> tuple[
    dict[int, str],  # category_id -> category_name
    dict[int, dict[str, Any]],  # video_id -> video_info
    dict[int, list[dict[str, Any]]],  # video_id -> list of image_info sorted by frame order
    dict[int, list[dict[str, Any]]],  # image_id -> list of annotations
    dict[int, dict[str, Any]],  # image_id -> image_info
]:
    """Build lookup indexes from a loaded COCO annotation dictionary.

    Args:
        coco_annotation: Parsed COCO JSON as a Python dictionary.

    Returns:
        Tuple of:
        - ``categories``: ``{category_id: name}`` mapping.
        - ``videos``: ``{video_id: video_info}`` mapping.
        - ``images_by_video``: ``{video_id: [image_info, ...]}`` sorted by frame order.
        - ``anns_by_image``: ``{image_id: [annotation, ...]}`` mapping.
        - ``image_by_id``: ``{image_id: image_info}`` mapping.
    """
    categories: dict[int, str] = {
        c["id"]: c.get("name", f"cat_{c['id']}") for c in coco_annotation.get("categories", [])
    }
    images_by_video: dict[int, list[dict[str, Any]]] = defaultdict(list)
    anns_by_image: dict[int, list[dict[str, Any]]] = defaultdict(list)

    for ann in coco_annotation.get("annotations", []):
        anns_by_image[ann["image_id"]].append(ann)

    image_by_id: dict[int, dict[str, Any]] = {}
    for img in coco_annotation.get("images", []):
        image_by_id[img["id"]] = img
        images_by_video[img.get("video_id", -1)].append(img)

    for vid in images_by_video:
        images_by_video[vid].sort(key=lambda x: (x.get("frame_id", x["id"]), x["id"]))

    videos: dict[int, dict[str, Any]] = {v["id"]: v for v in coco_annotation.get("videos", [])}
    return categories, videos, images_by_video, anns_by_image, image_by_id


def _annotate_frame(
    frame: Any,
    img_info: dict[str, Any],
    anns: list[dict[str, Any]],
    categories: dict[int, str],
) -> Any:
    """Overlay COCO annotations onto a single video frame.

    Draws a header bar with image/frame/video IDs, bounding boxes for each
    annotation, and a label showing category, track ID, range, and horizon flag.

    Args:
        frame: BGR image array as returned by ``cv2.imread``.
        img_info: COCO image record for this frame.
        anns: List of COCO annotation records whose ``image_id`` matches this frame.
        categories: ``{category_id: name}`` mapping used to resolve labels.

    Returns:
        The input frame array with annotations drawn in place.
    """
    h, w = frame.shape[:2]

    header = (
        f"image_id={img_info.get('id')} "
        f"frame_id={img_info.get('frame_id', 'NA')} "
        f"video_id={img_info.get('video_id', 'NA')}"
    )
    cv2.rectangle(frame, (0, 0), (w, 30), (0, 0, 0), -1)
    cv2.putText(
        frame, header, (8, 20), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 1, cv2.LINE_AA
    )

    for ann in anns:
        bbox = ann.get("bbox", [])
        if len(bbox) != 4:
            continue

        x, y, bw, bh = bbox
        x1, y1 = int(x), int(y)
        x2, y2 = int(x + bw), int(y + bh)

        x1 = max(0, min(w - 1, x1))
        y1 = max(0, min(h - 1, y1))
        x2 = max(0, min(w - 1, x2))
        y2 = max(0, min(h - 1, y2))

        cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)

        category_id = ann.get("category_id")
        if category_id is None:
            continue

        category_name = categories.get(category_id, str(category_id))
        track_id = ann.get("track_id", "NA")
        range_m = ann.get("range_m", "NA")
        above_h = ann.get("is_above_horizon", "NA")

        label = f"{category_name} | track={track_id} | range={range_m}m | above_h={above_h}"
        ty = max(15, y1 - 8)
        cv2.rectangle(frame, (x1, max(0, ty - 15)), (min(w - 1, x1 + 520), ty + 2), (0, 0, 0), -1)
        cv2.putText(
            frame,
            label,
            (x1 + 2, ty),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.45,
            (0, 255, 255),
            1,
            cv2.LINE_AA,
        )

    return frame


def _infer_size_from_imgs(imgs, base_image_path) -> tuple[int, int]:
    """Infer frame dimensions from the first readable image.

    Args:
        imgs: List of COCO image records.
        base_image_path: Root directory for resolving image paths.

    Returns:
        Tuple of ``(height, width)``.

    Raises:
        RuntimeError: If no readable frame is found.
    """
    first_frame = None
    for img_info in imgs:
        filename = img_info.get("filename") or img_info.get("file_name")
        if not filename:
            continue
        try:
            img_path = _resolve_image_path(base_image_path, filename)
        except FileNotFoundError:
            # logger.warning(f"Missing image: {filename}")
            continue
        first_frame = cv2.imread(str(img_path))
        if first_frame is not None:
            break

    if first_frame is None:
        raise RuntimeError("No readable frames found to infer size")

    return first_frame.shape[:2]


def generate_annotated_videos(
    annotations_json: str,
    base_image_path: str,
    output_dir: str,
) -> None:
    """Render annotated MP4 videos from a COCO-format annotation file.

    For each video entry in the COCO annotation, assembles the corresponding
    image frames in order, draws bounding boxes and metadata overlays via
    :func:`_annotate_frame`, and writes an ``mp4v``-encoded MP4 file.

    Args:
        annotations_json: Path to the COCO JSON annotation file.
        base_image_path: Root directory used to resolve relative image paths
            stored in the annotation.
        output_dir: Directory where output MP4 files will be written.
            Created if it does not exist.
    """
    with open(annotations_json) as f:
        coco_annotation = json.load(f)

    categories, videos, images_by_video, anns_by_image, _ = _build_indexes(coco_annotation)

    output_dir_path = Path(output_dir)
    output_dir_path.mkdir(parents=True, exist_ok=True)

    for video_id, imgs in tqdm(images_by_video.items(), desc="Processing videos", unit="video"):
        if not imgs:
            continue

        video_info = videos.get(video_id, {})
        fps = float(video_info.get("fps", 10.0))

        height, width = video_info.get("height"), video_info.get("width")

        if height is None or width is None:
            try:
                height, width = _infer_size_from_imgs(imgs, base_image_path)
            except RuntimeError:
                # logger.error(f"Cannot infer size for video_id={video_id}: {e}")
                continue

        frames_written = 0
        video_name = video_info.get("file_name")
        if video_name:
            video_name = Path(video_name).stem
        else:
            video_name = video_id
        out_path = output_dir_path / f"video_{video_name}.mp4"

        fourcc = cv2.VideoWriter_fourcc(*"mp4v")  # type: ignore[attr-defined]
        writer = cv2.VideoWriter(str(out_path), fourcc, fps, (width, height))

        for img_info in imgs:
            filename = img_info.get("filename") or img_info.get("file_name")
            if not filename:
                continue
            try:
                img_path = _resolve_image_path(base_image_path, filename)
            except FileNotFoundError:
                # logger.warning(f"Missing image: {filename}")
                continue

            frame = cv2.imread(str(img_path))
            if frame is None:
                logger.warning(f"Cannot read image: {img_path}")
                continue

            anns = anns_by_image.get(img_info["id"], [])
            annotated = _annotate_frame(frame, img_info, anns, categories)
            writer.write(annotated)
            frames_written += 1

        writer.release()

        if frames_written == 0:
            logger.warning(f"No frames written for video_id={video_id}, skipping output")
            try:
                if out_path.exists():
                    out_path.unlink()
            except Exception:
                pass
            continue

        logger.info(f"Wrote annotated video to {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate annotated videos from a COCO-format annotation file."
    )
    parser.add_argument(
        "--annotations_json",
        required=True,
        help="Path to the COCO JSON annotation file.",
    )
    parser.add_argument(
        "--base_image_path",
        required=True,
        help="Root directory used to resolve relative image paths in the annotation.",
    )
    parser.add_argument(
        "--output_dir",
        default="data/annotated_videos",
        help="Directory where output MP4 files will be written.",
    )
    args = parser.parse_args()

    generate_annotated_videos(args.annotations_json, args.base_image_path, args.output_dir)


if __name__ == "__main__":
    main()
