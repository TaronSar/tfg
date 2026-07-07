import argparse
from pathlib import Path

from loguru import logger

from src.preprocessing.utils.coco_json_io import load_coco_json, save_coco_json


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Remove COCO images (and related annotations) not found in a storage path."
    )
    parser.add_argument("--input-json", required=True, help="Path to input COCO JSON")
    parser.add_argument("--output-json", required=True, help="Path to output COCO JSON")
    parser.add_argument(
        "--images-root",
        required=True,
        help="Root directory where image files are stored",
    )
    return parser.parse_args()


def image_exists(images_root: Path, file_name: str) -> bool:
    """Check whether an image file exists under the given root.

    Args:
        images_root: Root directory for image files.
        file_name: Relative image file name.

    Returns:
        True if the file exists.
    """
    return (images_root / file_name).is_file()


def main() -> None:
    args = parse_args()

    input_json = Path(args.input_json)
    output_json = Path(args.output_json)
    images_root = Path(args.images_root)

    if not input_json.is_file():
        raise FileNotFoundError(f"Input JSON not found: {input_json}")
    if not images_root.is_dir():
        raise NotADirectoryError(f"Images root is not a directory: {images_root}")

    coco = load_coco_json(input_json)

    images = coco.get("images", [])
    annotations = coco.get("annotations", [])
    videos = coco.get("videos", [])
    tracks = coco.get("tracks", [])

    kept_images = [img for img in images if image_exists(images_root, img.get("file_name", ""))]
    kept_image_ids = {img["id"] for img in kept_images if "id" in img}
    kept_annotations = [ann for ann in annotations if ann.get("image_id") in kept_image_ids]

    # Clean up videos: keep only those still referenced by remaining images
    kept_video_ids = {img.get("video_id") for img in kept_images if img.get("video_id") is not None}
    kept_videos = [v for v in videos if v["id"] in kept_video_ids]

    # Clean up tracks: keep only those still referenced by remaining annotations
    kept_track_ids = {
        ann.get("track_id") for ann in kept_annotations if ann.get("track_id") is not None
    }
    kept_tracks = [t for t in tracks if t["id"] in kept_track_ids]

    coco["images"] = kept_images
    coco["annotations"] = kept_annotations
    coco["videos"] = kept_videos
    coco["tracks"] = kept_tracks

    save_coco_json(coco, output_json, indent=2)

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
    logger.info(f"Saved filtered COCO to: {output_json}")


if __name__ == "__main__":
    main()
