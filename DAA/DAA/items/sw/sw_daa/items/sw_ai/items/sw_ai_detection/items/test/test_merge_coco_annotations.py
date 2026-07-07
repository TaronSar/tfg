import copy

import pytest

from src.dataset.merge_coco_annotations import merge_coco

BASE_PATH_A = "/data/dataset_a"
BASE_PATH_B = "/data/dataset_b"

CATEGORIES_A = [
    {"id": 1, "name": "airplane", "supercategory": "object"},
    {"id": 2, "name": "helicopter", "supercategory": "object"},
]

CATEGORIES_B = [
    {"id": 1, "name": "helicopter", "supercategory": "object"},
    {"id": 2, "name": "drone", "supercategory": "object"},
]


def _make_coco(
    categories,
    videos,
    tracks,
    images,
    annotations,
    info=None,
):
    return {
        "info": info or {"description": "test"},
        "licenses": [],
        "categories": copy.deepcopy(categories),
        "videos": copy.deepcopy(videos),
        "tracks": copy.deepcopy(tracks),
        "images": copy.deepcopy(images),
        "annotations": copy.deepcopy(annotations),
    }


@pytest.fixture
def coco_a():
    return _make_coco(
        categories=CATEGORIES_A,
        videos=[
            {
                "id": 1,
                "file_name": "video_a/",
                "width": 1920,
                "height": 1080,
                "fps": 30,
                "num_frames": 100,
            },
        ],
        tracks=[
            {"id": 1, "category_id": 1, "video_id": 1},
            {"id": 2, "category_id": 2, "video_id": 1},
        ],
        images=[
            {
                "id": 1,
                "file_name": "video_a/frame_000.jpg",
                "width": 1920,
                "height": 1080,
                "video_id": 1,
                "frame_id": 0,
            },
            {
                "id": 2,
                "file_name": "video_a/frame_001.jpg",
                "width": 1920,
                "height": 1080,
                "video_id": 1,
                "frame_id": 1,
            },
        ],
        annotations=[
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [10, 20, 30, 40],
                "area": 1200,
                "iscrowd": 0,
                "segmentation": [],
                "track_id": 1,
                "range_m": 500.0,
                "is_above_horizon": 1,
            },
            {
                "id": 2,
                "image_id": 2,
                "category_id": 2,
                "bbox": [50, 60, 70, 80],
                "area": 5600,
                "iscrowd": 0,
                "segmentation": [],
                "track_id": 2,
                "range_m": 300.0,
                "is_above_horizon": 0,
            },
        ],
    )


@pytest.fixture
def coco_b():
    return _make_coco(
        categories=CATEGORIES_B,
        videos=[
            {
                "id": 1,
                "file_name": "video_b/",
                "width": 2448,
                "height": 2048,
                "fps": 10,
                "num_frames": 50,
            },
        ],
        tracks=[
            {"id": 1, "category_id": 1, "video_id": 1},
            {"id": 2, "category_id": 2, "video_id": 1},
        ],
        images=[
            {
                "id": 1,
                "file_name": "video_b/frame_000.jpg",
                "width": 2448,
                "height": 2048,
                "video_id": 1,
                "frame_id": 0,
            },
        ],
        annotations=[
            {
                "id": 1,
                "image_id": 1,
                "category_id": 1,
                "bbox": [100, 200, 50, 60],
                "area": 3000,
                "iscrowd": 0,
                "segmentation": [],
                "track_id": 1,
                "range_m": 1000.0,
                "is_above_horizon": -1,
            },
            {
                "id": 2,
                "image_id": 1,
                "category_id": 2,
                "bbox": [200, 300, 40, 30],
                "area": 1200,
                "iscrowd": 0,
                "segmentation": [],
                "track_id": 2,
                "range_m": -1.0,
                "is_above_horizon": 1,
            },
        ],
    )


class TestMergeCoco:
    def test_counts(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        assert len(merged["images"]) == 3
        assert len(merged["annotations"]) == 4
        assert len(merged["videos"]) == 2
        assert len(merged["tracks"]) == 4

    def test_categories_unified_by_name(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        cat_names = {c["name"] for c in merged["categories"]}
        assert cat_names == {"airplane", "helicopter", "drone"}

    def test_no_duplicate_ids(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        for key in ("images", "annotations", "videos", "tracks", "categories"):
            ids = [item["id"] for item in merged[key]]
            assert len(ids) == len(set(ids)), f"Duplicate IDs in {key}: {ids}"

    def test_annotation_references_valid(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        image_ids = {img["id"] for img in merged["images"]}
        cat_ids = {c["id"] for c in merged["categories"]}
        track_ids = {t["id"] for t in merged["tracks"]}
        for ann in merged["annotations"]:
            assert ann["image_id"] in image_ids
            assert ann["category_id"] in cat_ids
            assert ann["track_id"] in track_ids

    def test_track_references_valid(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        video_ids = {v["id"] for v in merged["videos"]}
        cat_ids = {c["id"] for c in merged["categories"]}
        for track in merged["tracks"]:
            assert track["video_id"] in video_ids
            assert track["category_id"] in cat_ids

    def test_image_video_references_valid(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        video_ids = {v["id"] for v in merged["videos"]}
        for img in merged["images"]:
            assert img["video_id"] in video_ids

    def test_shared_category_reuses_id(self, coco_a, coco_b):
        """helicopter exists in both; merged annotations from B should use A's helicopter id."""
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        heli_id = next(c["id"] for c in merged["categories"] if c["name"] == "helicopter")
        # coco_b track 1 was helicopter (cat 1 in B) -> should map to heli_id
        # Find a track from B (video_id remapped to 2)
        b_tracks = [t for t in merged["tracks"] if t["video_id"] == 2]
        heli_track = [t for t in b_tracks if t["category_id"] == heli_id]
        assert len(heli_track) == 1

    def test_bbox_preserved(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        bboxes = [ann["bbox"] for ann in merged["annotations"]]
        assert [10, 20, 30, 40] in bboxes
        assert [100, 200, 50, 60] in bboxes

    def test_empty_b(self, coco_a):
        empty = _make_coco([], [], [], [], [])
        merged = merge_coco([coco_a, empty], [BASE_PATH_A, BASE_PATH_B])
        assert len(merged["images"]) == 2
        assert len(merged["annotations"]) == 2

    def test_empty_a(self, coco_b):
        empty = _make_coco([], [], [], [], [])
        merged = merge_coco([empty, coco_b], [BASE_PATH_A, BASE_PATH_B])
        assert len(merged["images"]) == 1
        assert len(merged["annotations"]) == 2

    def test_info_from_first(self, coco_a, coco_b):
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        assert merged["info"] == coco_a["info"]

    def test_image_paths_rebased_common_parent(self, coco_a, coco_b):
        """Image paths should be relative to the common ancestor of base paths."""
        merged = merge_coco([coco_a, coco_b], [BASE_PATH_A, BASE_PATH_B])
        file_names = [img["file_name"] for img in merged["images"]]
        assert "dataset_a/video_a/frame_000.jpg" in file_names
        assert "dataset_a/video_a/frame_001.jpg" in file_names
        assert "dataset_b/video_b/frame_000.jpg" in file_names

    def test_image_paths_same_base(self, coco_a, coco_b):
        """When both datasets share the same base, paths stay unchanged."""
        merged = merge_coco([coco_a, coco_b], ["/data/shared", "/data/shared"])
        file_names = [img["file_name"] for img in merged["images"]]
        assert "video_a/frame_000.jpg" in file_names
        assert "video_b/frame_000.jpg" in file_names

    def test_image_paths_nested_bases(self, coco_a, coco_b):
        """One base path is a subdirectory of the other."""
        merged = merge_coco([coco_a, coco_b], ["/data/root", "/data/root/sub"])
        file_names_b = [
            img["file_name"] for img in merged["images"] if "video_b" in img["file_name"]
        ]
        assert all(fn.startswith("sub/") for fn in file_names_b)

    def test_image_paths_no_common_ancestor(self, coco_a, coco_b):
        """When base paths share only root, paths are absolute-like from /."""
        merged = merge_coco([coco_a, coco_b], ["/alpha/dataset_a", "/beta/dataset_b"])
        file_names = [img["file_name"] for img in merged["images"]]
        assert "alpha/dataset_a/video_a/frame_000.jpg" in file_names
        assert "beta/dataset_b/video_b/frame_000.jpg" in file_names

    def test_single_dataset(self, coco_a):
        """Merging a single dataset returns it with rebased paths."""
        merged = merge_coco([coco_a], [BASE_PATH_A])
        assert len(merged["images"]) == 2
        assert len(merged["annotations"]) == 2

    def test_three_datasets(self, coco_a, coco_b):
        """Merging three datasets produces correct counts and unique IDs."""
        coco_c = _make_coco(
            categories=[{"id": 1, "name": "airplane", "supercategory": "object"}],
            videos=[
                {
                    "id": 1,
                    "file_name": "video_c/",
                    "width": 640,
                    "height": 480,
                    "fps": 15,
                    "num_frames": 10,
                }
            ],
            tracks=[{"id": 1, "category_id": 1, "video_id": 1}],
            images=[
                {
                    "id": 1,
                    "file_name": "video_c/frame_000.jpg",
                    "width": 640,
                    "height": 480,
                    "video_id": 1,
                    "frame_id": 0,
                }
            ],
            annotations=[
                {
                    "id": 1,
                    "image_id": 1,
                    "category_id": 1,
                    "bbox": [0, 0, 10, 10],
                    "area": 100,
                    "iscrowd": 0,
                    "segmentation": [],
                    "track_id": 1,
                }
            ],
        )
        merged = merge_coco(
            [coco_a, coco_b, coco_c],
            [BASE_PATH_A, BASE_PATH_B, "/data/dataset_c"],
        )
        assert len(merged["images"]) == 4
        assert len(merged["annotations"]) == 5
        assert len(merged["videos"]) == 3
        for key in ("images", "annotations", "videos", "tracks", "categories"):
            ids = [item["id"] for item in merged[key]]
            assert len(ids) == len(set(ids)), f"Duplicate IDs in {key}"
