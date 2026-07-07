from typing import Any


def filter_coco_by_image_ids(
    coco: dict[str, Any],
    keep_ids: set[int],
) -> dict[str, Any]:
    """Return a COCO dict restricted to the given image IDs.

    Annotations, videos, and tracks are filtered to match.

    Args:
        coco: Source COCO dict.
        keep_ids: Image IDs to keep.

    Returns:
        New COCO dict containing only images in ``keep_ids``.
    """
    images = [img for img in coco["images"] if img["id"] in keep_ids]
    kept_img_set = {img["id"] for img in images}

    annotations = [ann for ann in coco.get("annotations", []) if ann["image_id"] in kept_img_set]
    kept_video_ids = {img["video_id"] for img in images if "video_id" in img}
    videos = [v for v in coco.get("videos", []) if v["id"] in kept_video_ids]

    kept_track_ids = {ann["track_id"] for ann in annotations if "track_id" in ann}
    tracks = [t for t in coco.get("tracks", []) if t["id"] in kept_track_ids]

    out: dict[str, Any] = {
        k: v for k, v in coco.items() if k not in ("images", "annotations", "videos", "tracks")
    }
    out["images"] = images
    out["annotations"] = annotations
    if videos:
        out["videos"] = videos
    if tracks:
        out["tracks"] = tracks
    return out
