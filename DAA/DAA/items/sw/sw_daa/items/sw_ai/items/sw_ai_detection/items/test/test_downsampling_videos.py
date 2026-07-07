import copy
import math
from collections import Counter

import pytest

from src.preprocessing.downsampling_videos import (
    downsample_coco,
    downsample_images,
    group_images_by_video_or_folder,
)

CATEGORIES = [
    {"id": 1, "name": "airplane", "supercategory": "object"},
    {"id": 2, "name": "helicopter", "supercategory": "object"},
]

VIDEOS = [
    {
        "id": 500,
        "file_name": "0001ba865c8e410e88609541b8f55ffc/",
        "width": 2448,
        "height": 2048,
        "fps": 10.0,
        "num_frames": 1199,
    },
    {
        "id": 526,
        "file_name": "000c3ab11ab5407dab8e0bade68e1cb4/",
        "width": 2448,
        "height": 2048,
        "fps": 10.0,
        "num_frames": 1199,
    },
    {
        "id": 605,
        "file_name": "0017e41d49c74b60b7cb3be88ae76088/",
        "width": 2448,
        "height": 2048,
        "fps": 10.0,
        "num_frames": 1199,
    },
]

TRACKS = [
    {"id": 1337, "category_id": 2, "video_id": 500},
    {"id": 1338, "category_id": 1, "video_id": 526},
    {"id": 1339, "category_id": 1, "video_id": 605},
    {"id": 1340, "category_id": 2, "video_id": 605},
]

NUM_FRAMES_PER_VIDEO = 1199


@pytest.fixture()
def fake_coco() -> dict:
    """Build a COCO dict that mirrors the real airborne tracking dataset."""
    images = []
    annotations = []
    img_id = 0
    ann_id = 0

    video_tracks: dict[int, list[dict]] = {}
    for t in TRACKS:
        video_tracks.setdefault(t["video_id"], []).append(t)

    for video in VIDEOS:
        vid: int = video["id"]  # type: ignore[assignment]
        folder = video["file_name"]
        for frame_idx in range(NUM_FRAMES_PER_VIDEO):
            frame_id = frame_idx + 2  # real dataset starts at frame_id=2
            img_id += 1
            images.append(
                {
                    "id": img_id,
                    "width": video["width"],
                    "height": video["height"],
                    "file_name": f"{folder}{frame_id:020d}.png",
                    "video_id": vid,
                    "frame_id": frame_id,
                }
            )
            # Sparse annotations (every 6th frame) to mimic real data
            if frame_idx % 6 == 0:
                for trk in video_tracks.get(vid, []):
                    ann_id += 1
                    annotations.append(
                        {
                            "id": ann_id,
                            "category_id": trk["category_id"],
                            "iscrowd": 0,
                            "segmentation": [],
                            "image_id": img_id,
                            "area": 36.0,
                            "bbox": [100.0, 200.0, 6.0, 6.0],
                            "track_id": trk["id"],
                            "range_m": 1937.34,
                            "is_above_horizon": -1,
                        }
                    )

    return {
        "info": {"description": "Fake airborne tracking COCO"},
        "licenses": [],
        "images": images,
        "annotations": annotations,
        "categories": list(CATEGORIES),
        "videos": [dict(v) for v in VIDEOS],
        "tracks": [dict(t) for t in TRACKS],
    }


class TestGroupImagesByVideoOrFolder:
    """Tests for ``group_images_by_video_or_folder``."""

    def test_groups_by_video_id(self):
        images = [
            {"id": 1, "file_name": "a/f1.png", "video_id": 10},
            {"id": 2, "file_name": "a/f2.png", "video_id": 10},
            {"id": 3, "file_name": "b/f1.png", "video_id": 20},
        ]
        groups = group_images_by_video_or_folder(images)

        assert set(groups.keys()) == {10, 20}
        assert len(groups[10]) == 2  # type: ignore
        assert len(groups[20]) == 1  # type: ignore

    def test_groups_by_folder_when_no_video_id(self):
        images = [
            {"id": 1, "file_name": "folderA/f1.png"},
            {"id": 2, "file_name": "folderA/f2.png"},
            {"id": 3, "file_name": "folderB/f1.png"},
        ]
        groups = group_images_by_video_or_folder(images)

        assert set(groups.keys()) == {"folderA", "folderB"}


class TestDownsampleImages:
    """Tests for ``downsample_images``."""

    def test_keeps_every_nth_by_frame_id(self):
        images = [{"id": i, "frame_id": i, "file_name": f"{i}.png"} for i in range(10)]
        result = downsample_images(images, keep_every=3)

        assert [img["frame_id"] for img in result] == [0, 3, 6, 9]

    def test_keeps_every_nth_by_filename(self):
        images = [{"id": i, "file_name": f"frame_{i:03d}.png"} for i in range(5)]
        result = downsample_images(images, keep_every=2)

        assert len(result) == 3

    def test_keep_every_1_returns_all(self):
        images = [{"id": i, "frame_id": i} for i in range(7)]
        result = downsample_images(images, keep_every=1)

        assert len(result) == 7


class TestDownsampleCoco:
    """Functional tests for ``downsample_coco`` using the full fake dataset."""

    def test_keeps_correct_frame_count(self, fake_coco):
        keep_every = 10
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every)

        expected_per_video = math.ceil(NUM_FRAMES_PER_VIDEO / keep_every)
        frames_per_video = Counter(img["video_id"] for img in result["images"])

        assert len(frames_per_video) == len(VIDEOS)
        for vid_id, count in frames_per_video.items():
            assert count == expected_per_video, (
                f"Video {vid_id}: expected {expected_per_video}, got {count}"
            )

    def test_removes_orphan_annotations(self, fake_coco):
        keep_every = 10
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every)
        kept_image_ids = {img["id"] for img in result["images"]}

        for ann in result["annotations"]:
            assert ann["image_id"] in kept_image_ids

        assert 0 < len(result["annotations"]) < len(fake_coco["annotations"])

    def test_fixes_videos(self, fake_coco):
        keep_every = 10
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every)

        out_video_ids = {v["id"] for v in result["videos"]}
        referenced_video_ids = {img["video_id"] for img in result["images"]}
        assert out_video_ids == referenced_video_ids

    def test_num_frames_recalculated(self, fake_coco):
        keep_every = 10
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every)

        frames_per_video = Counter(img["video_id"] for img in result["images"])
        for video in result["videos"]:
            assert video["num_frames"] == frames_per_video[video["id"]]

    def test_fixes_tracks(self, fake_coco):
        keep_every = 10
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every)

        out_track_ids = {t["id"] for t in result["tracks"]}
        referenced_track_ids = {ann["track_id"] for ann in result["annotations"]}
        assert out_track_ids == referenced_track_ids

    def test_preserves_frame_order(self, fake_coco):
        keep_every = 10
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every)

        for video in VIDEOS:
            vid = video["id"]
            frame_ids = sorted(
                img["frame_id"] for img in result["images"] if img["video_id"] == vid
            )
            gaps = [frame_ids[i + 1] - frame_ids[i] for i in range(len(frame_ids) - 1)]
            assert all(g == keep_every for g in gaps), f"Video {vid}: non-uniform gaps {set(gaps)}"

    def test_categories_unchanged(self, fake_coco):
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every=5)

        assert result["categories"] == fake_coco["categories"]

    def test_keep_every_1_is_identity(self, fake_coco):
        original_len = len(fake_coco["images"])
        result = downsample_coco(copy.deepcopy(fake_coco), keep_every=1)

        assert len(result["images"]) == original_len
        assert len(result["annotations"]) == len(fake_coco["annotations"])

    def test_invalid_keep_every_raises(self, fake_coco):
        with pytest.raises(ValueError, match="must be >= 1"):
            downsample_coco(fake_coco, keep_every=0)
