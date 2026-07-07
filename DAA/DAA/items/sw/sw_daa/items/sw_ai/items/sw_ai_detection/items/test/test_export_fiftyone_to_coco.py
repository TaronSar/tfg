import json
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

import fiftyone

# Stub attributes the source module accesses at import time, before
# any fixture has a chance to patch them.
if not hasattr(fiftyone, "ViewField"):
    fiftyone.ViewField = MagicMock()
if not hasattr(fiftyone, "config"):
    fiftyone.config = types.SimpleNamespace(database_uri=None)


def _make_metadata(width: int = 640, height: int = 480) -> MagicMock:
    meta = MagicMock()
    meta.width = width
    meta.height = height
    return meta


def _make_detection(
    label: str = "airplane",
    bbox: tuple = (0.1, 0.1, 0.2, 0.2),
    index: int = 1,
    score: float | None = None,
    **extra_fields,
) -> MagicMock:
    det = MagicMock()
    det.label = label
    det.bounding_box = list(bbox)
    det.index = index
    det.confidence = score

    for key, value in extra_fields.items():
        setattr(det, key, value)

    # Mimic fo.Detection.field_names — standard fields + any custom ones
    standard = ("id", "label", "bounding_box", "confidence", "index", "tags", "attributes")
    det.field_names = standard + tuple(extra_fields.keys())
    # Make det[key] resolve to the actual attribute value
    det.__getitem__ = MagicMock(side_effect=lambda key: getattr(det, key, None))

    return det


def _make_sample(
    filepath: str = "/images/video1/frame_001.jpg",
    coco_image_id: int = 1,
    video_id: int = 1,
    frame_id: int = 0,
    video_path: str = "video1.mp4",
    video_fps: int = 10,
    video_num_frames: int = 100,
    detections: list | None = None,
    tags: list[str] | None = None,
) -> MagicMock:
    sample = MagicMock()
    sample.filepath = filepath
    sample.coco_image_id = coco_image_id
    sample.metadata = _make_metadata()
    sample.tags = tags or []

    # has_field always returns True for known fields; False otherwise
    known_fields = {
        "coco_image_id",
        "video_id",
        "frame_id",
        "video_path",
        "video_fps",
        "video_num_frames",
        "ground_truth",
    }
    sample.has_field = lambda f: f in known_fields

    field_values = {
        "video_id": video_id,
        "frame_id": frame_id,
        "video_path": video_path,
        "video_fps": video_fps,
        "video_num_frames": video_num_frames,
    }
    sample.get_field = lambda f: field_values.get(f)

    gt = MagicMock()
    gt.detections = detections if detections is not None else [_make_detection()]
    sample.ground_truth = gt

    return sample


def _make_dataset(samples: list) -> MagicMock:
    dataset = MagicMock()
    dataset.iter_samples = lambda: iter(samples)
    return dataset


MOCK_CLASSES = ["airplane", "helicopter", "bird"]


@pytest.fixture(autouse=True)
def patch_fo(monkeypatch):
    """Prevent any real FiftyOne / MongoDB connection."""
    fake_fo = types.SimpleNamespace(
        config=types.SimpleNamespace(database_uri=None),
    )
    monkeypatch.setattr("src.fiftyone.export_fiftyone_to_coco.fo", fake_fo)


def _run_export(
    samples: list,
    tmp_path: Path,
    images_dir: str | None = None,
    classes: list[str] | None = None,
) -> dict:
    from src.fiftyone.export_fiftyone_to_coco import export_fiftyone_to_extended_coco

    out = str(tmp_path / "out.json")
    export_fiftyone_to_extended_coco(
        dataset=_make_dataset(samples),
        output_json=out,
        classes=classes or MOCK_CLASSES,
        images_dir=images_dir,
        version="test",
    )
    with open(out) as f:
        return json.load(f)


class TestBuildCategories:
    def test_categories_match_schema(self):
        from src.preprocessing.utils.coco_json_io import build_categories

        categories, name_to_id = build_categories(["airplane", "helicopter", "bird"])
        assert [c["name"] for c in categories] == ["airplane", "helicopter", "bird"]
        assert name_to_id["airplane"] == 1
        assert name_to_id["bird"] == 3

    def test_ids_are_sequential_from_one(self):
        from src.preprocessing.utils.coco_json_io import build_categories

        categories, _ = build_categories(["airplane", "helicopter", "bird"])
        assert [c["id"] for c in categories] == list(range(1, len(categories) + 1))


class TestExportImages:
    def test_single_sample_produces_one_image(self, tmp_path):
        coco = _run_export([_make_sample()], tmp_path)
        assert len(coco["images"]) == 1

    def test_image_id_is_sequential(self, tmp_path):
        coco = _run_export([_make_sample(coco_image_id=42)], tmp_path)
        assert coco["images"][0]["id"] == 1

    def test_image_ids_sequential_across_samples(self, tmp_path):
        samples = [_make_sample(coco_image_id=i, filepath=f"/img/{i}.jpg") for i in range(1, 4)]
        coco = _run_export(samples, tmp_path)
        assert [img["id"] for img in coco["images"]] == [1, 2, 3]

    def test_duplicate_coco_image_ids_produce_unique_export_ids(self, tmp_path):
        """Samples from different COCO files may share coco_image_id; export must not collide."""
        samples = [
            _make_sample(coco_image_id=1, filepath="/img/a.jpg"),
            _make_sample(coco_image_id=1, filepath="/img/b.jpg"),
        ]
        coco = _run_export(samples, tmp_path)
        ids = [img["id"] for img in coco["images"]]
        assert len(ids) == len(set(ids))

    def test_image_filepath_absolute_when_no_images_dir(self, tmp_path):
        coco = _run_export([_make_sample(filepath="/abs/path/frame.jpg")], tmp_path)
        assert coco["images"][0]["file_name"] == "/abs/path/frame.jpg"

    def test_image_filepath_relative_when_images_dir_provided(self, tmp_path):
        coco = _run_export(
            [_make_sample(filepath="/data/images/video1/frame.jpg")],
            tmp_path,
            images_dir="/data/images",
        )
        assert coco["images"][0]["file_name"] == "video1/frame.jpg"

    def test_image_filepath_absolute_fallback_when_not_under_images_dir(self, tmp_path):
        coco = _run_export(
            [_make_sample(filepath="/other/path/frame.jpg")],
            tmp_path,
            images_dir="/data/images",
        )
        assert coco["images"][0]["file_name"] == "/other/path/frame.jpg"

    def test_multiple_samples_produce_correct_image_count(self, tmp_path):
        samples = [_make_sample(coco_image_id=i, filepath=f"/img/{i}.jpg") for i in range(1, 6)]
        coco = _run_export(samples, tmp_path)
        assert len(coco["images"]) == 5


class TestExportAnnotations:
    def test_single_detection_produces_one_annotation(self, tmp_path):
        coco = _run_export([_make_sample()], tmp_path)
        assert len(coco["annotations"]) == 1

    def test_annotation_category_id_matches_label(self, tmp_path):
        coco = _run_export(
            [_make_sample(detections=[_make_detection(label="helicopter")])], tmp_path
        )
        assert coco["annotations"][0]["category_id"] == 2  # helicopter → id 2 in mock schema

    def test_bbox_converted_to_absolute_pixels(self, tmp_path):
        # metadata is 640×480, bbox is relative [0.1, 0.1, 0.2, 0.2]
        coco = _run_export(
            [_make_sample(detections=[_make_detection(bbox=(0.1, 0.1, 0.2, 0.2))])], tmp_path
        )
        ann = coco["annotations"][0]
        assert ann["bbox"] == pytest.approx([64.0, 48.0, 128.0, 96.0])

    def test_range_m_and_above_horizon_preserved(self, tmp_path):
        coco = _run_export(
            [_make_sample(detections=[_make_detection(range_m=200.5, is_above_horizon=1)])],
            tmp_path,
        )
        ann = coco["annotations"][0]
        assert ann["range_m"] == pytest.approx(200.5)
        assert ann["is_above_horizon"] == 1

    def test_unknown_label_registered_dynamically(self, tmp_path):
        coco = _run_export([_make_sample(detections=[_make_detection(label="ufo")])], tmp_path)
        names = [c["name"] for c in coco["categories"]]
        assert "ufo" in names
        ann_cat_id = coco["annotations"][0]["category_id"]
        assert any(c["id"] == ann_cat_id and c["name"] == "ufo" for c in coco["categories"])

    def test_no_annotations_when_no_detections(self, tmp_path):
        coco = _run_export([_make_sample(detections=[])], tmp_path)
        assert coco["annotations"] == []


class TestExportVideos:
    def test_single_video_entry_for_shared_video_id(self, tmp_path):
        samples = [
            _make_sample(coco_image_id=i, filepath=f"/img/{i}.jpg", video_id=1, frame_id=i)
            for i in range(1, 4)
        ]
        coco = _run_export(samples, tmp_path)
        assert len(coco["videos"]) == 1

    def test_multiple_videos_produce_correct_video_count(self, tmp_path):
        samples = [
            _make_sample(coco_image_id=1, filepath="/img/1.jpg", video_id=1),
            _make_sample(coco_image_id=2, filepath="/img/2.jpg", video_id=2),
        ]
        coco = _run_export(samples, tmp_path)
        assert len(coco["videos"]) == 2

    def test_video_metadata_fields_present(self, tmp_path):
        coco = _run_export(
            [_make_sample(video_path="myvideo.mp4", video_fps=30, video_num_frames=500)], tmp_path
        )
        video = coco["videos"][0]
        assert video["file_name"] == "myvideo.mp4"
        assert video["fps"] == 30
        assert video["num_frames"] == 500


class TestExportTracks:
    def test_track_created_for_detection_with_index(self, tmp_path):
        coco = _run_export([_make_sample(detections=[_make_detection(index=5)])], tmp_path)
        assert len(coco["tracks"]) == 1

    def test_track_id_referenced_in_annotation(self, tmp_path):
        coco = _run_export([_make_sample()], tmp_path)
        track_id = coco["tracks"][0]["id"]
        assert coco["annotations"][0]["track_id"] == track_id

    def test_same_track_index_across_frames_produces_one_track(self, tmp_path):
        det = _make_detection(index=7)
        samples = [
            _make_sample(coco_image_id=i, filepath=f"/img/{i}.jpg", frame_id=i, detections=[det])
            for i in range(1, 4)
        ]
        coco = _run_export(samples, tmp_path)
        assert len(coco["tracks"]) == 1
        assert len(coco["annotations"]) == 3


class TestOutputFile:
    def test_output_file_created(self, tmp_path):
        out = tmp_path / "sub" / "out.json"
        from src.fiftyone.export_fiftyone_to_coco import export_fiftyone_to_extended_coco

        export_fiftyone_to_extended_coco(
            dataset=_make_dataset([_make_sample()]),
            output_json=str(out),
            classes=MOCK_CLASSES,
            version="test",
        )
        assert out.exists()

    def test_output_is_valid_json(self, tmp_path):
        coco = _run_export([_make_sample()], tmp_path)
        assert isinstance(coco, dict)

    def test_top_level_keys_present(self, tmp_path):
        coco = _run_export([_make_sample()], tmp_path)
        for key in ("info", "images", "annotations", "categories", "videos", "tracks"):
            assert key in coco
