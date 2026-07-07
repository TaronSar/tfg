import copy

import pytest

CATEGORIES = [
    {"id": 1, "name": "airplane", "supercategory": "object"},
    {"id": 2, "name": "helicopter", "supercategory": "object"},
    {"id": 3, "name": "bird", "supercategory": "object"},
]

_SIZE_LABELS = ("small", "medium", "large")


def make_coco(
    parts: list[tuple[str, int]] | None = None,
    frames_per_video: int = 10,
    ann_every: int = 2,
    n_duplicate_flights: int = 0,
) -> dict:
    """Build a minimal synthetic COCO dataset for testing.

    Args:
        parts: ``[(prefix, n_videos), ...]``. Default: part1×3, part2×3, part3×2.
        frames_per_video: Number of frames (images) per video.
        ann_every: Annotate every N-th frame.
        n_duplicate_flights: Number of flights from the first part to duplicate
            into the last part (simulates two cameras on the same encounter).

    Returns:
        COCO dict with ``videos``, ``tracks``, ``images``, and ``annotations``.
    """
    if parts is None:
        parts = [("part1", 3), ("part2", 3), ("part3", 2)]

    # bbox side lengths that map to small / medium / large area bins
    _SIZES = [6.0, 50.0, 200.0]  # area: 36, 2500, 40000

    videos, tracks, images, annotations = [], [], [], []
    vid_id = trk_id = img_id = ann_id = 0
    duplicates_remaining = n_duplicate_flights
    last_part = parts[-1][0]
    flight_idx = 0

    for part_name, n_videos in parts:
        for _ in range(n_videos):
            flight_idx += 1
            vid_hash = f"{flight_idx:032x}"

            # For the first n_duplicate_flights of the first part, create
            # the flight in both this part and the last part (second camera).
            flight_parts = [part_name]
            if part_name == parts[0][0] and duplicates_remaining > 0:
                duplicates_remaining -= 1
                flight_parts.append(last_part)

            for cam, fp in enumerate(flight_parts):
                vid_id += 1
                cam_suffix = f"_cam{cam}" if cam > 0 else ""
                videos.append(
                    {
                        "id": vid_id,
                        "file_name": f"{vid_hash}/",
                        "width": 2448,
                        "height": 2048,
                        "fps": 10.0,
                        "num_frames": frames_per_video,
                    }
                )

                trk_id += 1
                cat_id = (vid_id % len(CATEGORIES)) + 1
                tracks.append({"id": trk_id, "category_id": cat_id, "video_id": vid_id})

                for f in range(frames_per_video):
                    img_id += 1
                    images.append(
                        {
                            "id": img_id,
                            "width": 2448,
                            "height": 2048,
                            "file_name": f"{fp}/Images/{vid_hash}/{f:020d}{cam_suffix}.png",
                            "video_id": vid_id,
                            "frame_id": f,
                        }
                    )
                    if f % ann_every == 0:
                        ann_id += 1
                        size = _SIZES[f % 3]
                        annotations.append(
                            {
                                "id": ann_id,
                                "image_id": img_id,
                                "category_id": cat_id,
                                "bbox": [100.0, 100.0, size, size],
                                "area": size * size,
                                "size_category": _SIZE_LABELS[f % 3],
                                "iscrowd": 0,
                                "segmentation": [],
                                "track_id": trk_id,
                            }
                        )

    return {
        "info": {"description": "test"},
        "licenses": [],
        "categories": copy.deepcopy(CATEGORIES),
        "videos": videos,
        "tracks": tracks,
        "images": images,
        "annotations": annotations,
    }


@pytest.fixture
def coco():
    return make_coco()


@pytest.fixture
def coco_factory():
    return make_coco
