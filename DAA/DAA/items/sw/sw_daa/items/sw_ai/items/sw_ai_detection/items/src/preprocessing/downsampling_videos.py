import argparse
from pathlib import Path

from loguru import logger

from src.preprocessing.utils.coco_json_io import load_coco_json, save_coco_json


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed namespace with ``input_json``, ``output_json`` and
        ``keep_every`` attributes.
    """
    parser = argparse.ArgumentParser(
        description=(
            "Downsample images in a COCO (video-aware) annotation file by keeping "
            "every Nth frame per video/folder. Removes related annotations, "
            "and fixes videos/tracks accordingly."
        )
    )
    parser.add_argument("--input-json", required=True, help="Path to input COCO JSON")
    parser.add_argument("--output-json", required=True, help="Path to output COCO JSON")
    parser.add_argument(
        "--keep-every",
        type=int,
        default=2,
        help="Keep every Nth frame in each video/folder (N >= 1). Default: 2",
    )
    return parser.parse_args()


def group_images_by_video_or_folder(images: list[dict]) -> dict[str, list[dict]]:
    """Group images by ``video_id`` or, if absent, by parent folder.

    Args:
        images(list[dict]): List of COCO image dicts.

    Returns:
        Mapping from group key to list of image dicts.
    """
    groups: dict[str, list[dict]] = {}
    for img in images:
        key = img.get("video_id")
        if key is None:
            key = Path(img.get("file_name", "")).parent.as_posix()
        groups.setdefault(key, []).append(img)
    return groups


def downsample_images(images: list[dict], keep_every: int) -> list[dict]:
    """Keep every *keep_every*-th frame from a sorted list of images.

    Sorting uses ``frame_id`` when available, otherwise ``file_name``.

    Args:
        images(list[dict]): List of COCO image dicts belonging to a single video/folder.
        keep_every: Stride for frame selection (must be >= 1).

    Returns:
        Subset of *images* after downsampling.
    """
    if images and "frame_id" in images[0]:
        images_sorted = sorted(images, key=lambda x: x.get("frame_id", 0))
    else:
        images_sorted = sorted(images, key=lambda x: x.get("file_name", ""))
    return [img for i, img in enumerate(images_sorted) if i % keep_every == 0]


def _filter_annotations(annotations: list[dict], kept_image_ids: set[int]) -> list[dict]:
    """Keep only annotations whose ``image_id`` is in *kept_image_ids*."""
    return [ann for ann in annotations if ann.get("image_id") in kept_image_ids]


def _filter_videos(videos: list[dict], kept_images: list[dict]) -> list[dict]:
    """Keep only videos still referenced by *kept_images*."""
    kept_video_ids = {img.get("video_id") for img in kept_images if img.get("video_id") is not None}
    return [v for v in videos if v.get("id") in kept_video_ids]


def _recalculate_num_frames(videos: list[dict], images: list[dict]) -> None:
    """Update ``num_frames`` on each video based on the actual image count."""
    frames_per_video: dict[int, int] = {}
    for img in images:
        vid = img.get("video_id")
        if vid is not None:
            frames_per_video[vid] = frames_per_video.get(vid, 0) + 1
    for v in videos:
        v["num_frames"] = frames_per_video.get(v["id"], 0)


def _filter_tracks(tracks: list[dict], kept_annotations: list[dict]) -> list[dict]:
    """Keep only tracks still referenced by *kept_annotations*."""
    kept_track_ids = {
        ann.get("track_id") for ann in kept_annotations if ann.get("track_id") is not None
    }
    return [t for t in tracks if t.get("id") in kept_track_ids]


def downsample_coco(coco: dict, keep_every: int) -> dict:
    """Downsample a full COCO dict in-place and return it.

    Keeps every *keep_every*-th frame per video/folder and removes orphaned
    annotations, videos and tracks.

    Args:
        coco: COCO-format dictionary (images, annotations, videos, tracks, …).
        keep_every: Stride for frame selection (must be >= 1).

    Returns:
        The same *coco* dict with filtered lists.

    Raises:
        ValueError: If *keep_every* < 1.
    """
    if keep_every <= 0:
        raise ValueError("--keep-every must be >= 1")

    images = coco.get("images", [])
    annotations = coco.get("annotations", [])
    videos = coco.get("videos", [])
    tracks = coco.get("tracks", [])

    groups = group_images_by_video_or_folder(images)

    kept_images: list[dict] = []
    for _, imgs in groups.items():
        kept_images.extend(downsample_images(imgs, keep_every))

    kept_image_ids = {img["id"] for img in kept_images if "id" in img}
    kept_annotations = _filter_annotations(annotations, kept_image_ids)
    kept_videos = _filter_videos(videos, kept_images)
    _recalculate_num_frames(kept_videos, kept_images)
    kept_tracks = _filter_tracks(tracks, kept_annotations)

    coco["images"] = kept_images
    coco["annotations"] = kept_annotations
    coco["videos"] = kept_videos
    coco["tracks"] = kept_tracks

    logger.info(
        f"Input images: {len(images)}, kept: {len(kept_images)}, "
        f"removed: {len(images) - len(kept_images)}"
    )
    logger.info(
        f"Input annotations: {len(annotations)}, kept: {len(kept_annotations)}, "
        f"removed: {len(annotations) - len(kept_annotations)}"
    )
    logger.info(
        f"Input videos: {len(videos)}, kept: {len(kept_videos)}, "
        f"removed: {len(videos) - len(kept_videos)}"
    )
    logger.info(
        f"Input tracks: {len(tracks)}, kept: {len(kept_tracks)}, "
        f"removed: {len(tracks) - len(kept_tracks)}"
    )

    return coco


def main() -> None:
    args = parse_args()

    input_json = Path(args.input_json)
    output_json = Path(args.output_json)

    if not input_json.is_file():
        raise FileNotFoundError(f"Input JSON not found: {input_json}")

    coco = load_coco_json(input_json)

    coco = downsample_coco(coco, args.keep_every)

    save_coco_json(coco, output_json, indent=2)

    logger.info(f"Saved downsampled COCO to: {output_json}")


if __name__ == "__main__":
    main()
