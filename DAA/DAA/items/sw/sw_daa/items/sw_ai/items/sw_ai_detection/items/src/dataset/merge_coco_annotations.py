import argparse
from pathlib import Path
from typing import Any

from loguru import logger
from tqdm import tqdm

from src.preprocessing.utils.coco_json_io import load_coco_json, save_coco_json


def _max_id(items: list[dict[str, Any]]) -> int:
    """Return the maximum ``id`` in *items*, or 0 if empty."""
    return max((item["id"] for item in items), default=0)


def _remap_categories(
    merged_categories: list[dict[str, Any]],
    source_categories: list[dict[str, Any]],
) -> dict[int, int]:
    """Unify categories by name, appending new ones to *merged_categories*.

    Returns:
        Mapping from source category IDs to merged category IDs.
    """
    cat_name_to_id: dict[str, int] = {c["name"]: c["id"] for c in merged_categories}
    remap: dict[int, int] = {}
    next_id = _max_id(merged_categories) + 1
    for cat in source_categories:
        name = cat["name"]
        if name in cat_name_to_id:
            remap[cat["id"]] = cat_name_to_id[name]
        else:
            remap[cat["id"]] = next_id
            cat_name_to_id[name] = next_id
            merged_categories.append({**cat, "id": next_id})
            next_id += 1
    return remap


def _remap_videos(
    merged_videos: list[dict[str, Any]],
    source_videos: list[dict[str, Any]],
) -> dict[int, int]:
    """Append *source_videos* to *merged_videos* with remapped IDs.

    Returns:
        Mapping from source video IDs to merged video IDs.
    """
    remap: dict[int, int] = {}
    next_id = _max_id(merged_videos) + 1
    for video in source_videos:
        remap[video["id"]] = next_id
        merged_videos.append({**video, "id": next_id})
        next_id += 1
    return remap


def _remap_tracks(
    merged_tracks: list[dict[str, Any]],
    source_tracks: list[dict[str, Any]],
    cat_remap: dict[int, int],
    video_remap: dict[int, int],
) -> dict[int, int]:
    """Append *source_tracks* with remapped IDs, category IDs, and video IDs.

    Returns:
        Mapping from source track IDs to merged track IDs.
    """
    remap: dict[int, int] = {}
    next_id = _max_id(merged_tracks) + 1
    for track in source_tracks:
        remap[track["id"]] = next_id
        merged_tracks.append(
            {
                **track,
                "id": next_id,
                "category_id": cat_remap.get(track["category_id"], track["category_id"]),
                "video_id": video_remap.get(track["video_id"], track["video_id"]),
            }
        )
        next_id += 1
    return remap


def _rebase_file_name(file_name: str, base_path: Path, common_root: Path) -> str:
    """Rebase *file_name* from *base_path* so it is relative to *common_root*."""
    absolute = base_path / file_name
    return str(absolute.relative_to(common_root))


def _remap_images(
    merged_images: list[dict[str, Any]],
    source_images: list[dict[str, Any]],
    video_remap: dict[int, int],
    base_path: Path,
    common_root: Path,
) -> dict[int, int]:
    """Append *source_images* with remapped IDs and video IDs.

    Args:
        merged_images: Accumulator list of merged image dicts.
        source_images: Images from the source COCO dict to remap.
        video_remap: Mapping from source video IDs to merged video IDs.
        base_path: Base directory for source image paths.
        common_root: Common ancestor directory for rebasing paths.

    Returns:
        Mapping from source image IDs to merged image IDs.
    """
    remap: dict[int, int] = {}
    next_id = _max_id(merged_images) + 1
    for img in tqdm(source_images, desc="Remapping images", unit="img"):
        remap[img["id"]] = next_id
        file_name = img.get("file_name", "")
        file_name = _rebase_file_name(file_name, base_path, common_root)
        merged_images.append(
            {
                **img,
                "id": next_id,
                "file_name": file_name,
                "video_id": video_remap.get(img["video_id"], img["video_id"])
                if "video_id" in img
                else img.get("video_id"),
            }
        )
        next_id += 1
    return remap


def _remap_annotations(
    merged_annotations: list[dict[str, Any]],
    source_annotations: list[dict[str, Any]],
    image_remap: dict[int, int],
    cat_remap: dict[int, int],
    track_remap: dict[int, int],
) -> None:
    """Append *source_annotations* with remapped IDs and foreign keys."""
    next_id = _max_id(merged_annotations) + 1
    for ann in tqdm(source_annotations, desc="Remapping annotations", unit="ann"):
        merged_annotations.append(
            {
                **ann,
                "id": next_id,
                "image_id": image_remap.get(ann["image_id"], ann["image_id"]),
                "category_id": cat_remap.get(ann["category_id"], ann["category_id"]),
                "track_id": track_remap.get(ann["track_id"], ann["track_id"])
                if "track_id" in ann
                else ann.get("track_id"),
            }
        )
        next_id += 1


def merge_coco(
    coco_datasets: list[dict[str, Any]],
    images_base_paths: list[str],
) -> dict[str, Any]:
    """Merge multiple extended-COCO dictionaries into a single one.

    IDs in every dataset after the first are remapped so they never collide.

    Args:
        coco_datasets: List of COCO dicts to merge.
        images_base_paths: Base directory for image paths in each dataset.
            Must have the same length as *coco_datasets*.

    Returns:
        Merged COCO dict with image ``file_name`` values rebased
        relative to the common ancestor of all base paths.
    """
    resolved_bases = [Path(p).resolve() for p in images_base_paths]
    all_parts = [b.parts for b in resolved_bases]
    common_parts = list(all_parts[0])
    for parts in all_parts[1:]:
        common_parts = [pa for pa, pb in zip(common_parts, parts, strict=False) if pa == pb]
    common_root = Path(*common_parts) if common_parts else Path("/")

    first = coco_datasets[0]
    images_first = [
        {**img, "file_name": _rebase_file_name(img["file_name"], resolved_bases[0], common_root)}
        for img in first.get("images", [])
    ]

    merged = {
        "info": first.get("info", {}),
        "licenses": list(first.get("licenses", [])),
        "images": images_first,
        "annotations": list(first.get("annotations", [])),
        "categories": list(first.get("categories", [])),
        "videos": list(first.get("videos", [])),
        "tracks": list(first.get("tracks", [])),
    }

    for coco_next, base in zip(coco_datasets[1:], resolved_bases[1:], strict=False):
        merged["licenses"].extend(coco_next.get("licenses", []))
        cat_remap = _remap_categories(merged["categories"], coco_next.get("categories", []))
        video_remap = _remap_videos(merged["videos"], coco_next.get("videos", []))
        track_remap = _remap_tracks(
            merged["tracks"], coco_next.get("tracks", []), cat_remap, video_remap
        )
        image_remap = _remap_images(
            merged["images"], coco_next.get("images", []), video_remap, base, common_root
        )
        _remap_annotations(
            merged["annotations"],
            coco_next.get("annotations", []),
            image_remap,
            cat_remap,
            track_remap,
        )

    return merged


def merge_coco_files(
    inputs: list[str],
    images_base_paths: list[str],
    output: str,
) -> None:
    """Load multiple COCO JSON files, merge them, and write the result.

    Args:
        inputs: Paths to the COCO JSON files to merge.
        images_base_paths: Base directory for image paths in each file.
        output: Path for the merged output JSON file.
    """
    assert len(inputs) == len(images_base_paths), (
        "Number of input files must match number of base paths"
    )
    assert len(inputs) > 0, "At least one input file is required"

    coco_datasets = []
    for path in inputs:
        coco_datasets.append(load_coco_json(path))

    merged = merge_coco(coco_datasets, images_base_paths)

    save_coco_json(merged, output, indent=2)

    total_images = sum(len(d.get("images", [])) for d in coco_datasets)
    logger.info(
        f"Merged {total_images} images from {len(inputs)} files "
        f"-> {len(merged['images'])} images written to {output}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge multiple COCO JSON annotation files.")
    parser.add_argument("--inputs", nargs="+", required=True, help="COCO JSON files to merge")
    parser.add_argument(
        "--images_base_paths",
        nargs="+",
        required=True,
        help="Base path for images in each JSON (same order as --inputs)",
    )
    parser.add_argument("--output", required=True, help="Output merged COCO JSON file")
    args = parser.parse_args()
    merge_coco_files(args.inputs, args.images_base_paths, args.output)


if __name__ == "__main__":
    main()
