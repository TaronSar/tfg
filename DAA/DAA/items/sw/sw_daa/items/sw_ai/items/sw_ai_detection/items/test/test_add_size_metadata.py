import pytest

from src.preprocessing.add_size_metadata import add_size_metadata

_SMALL = 100
_MEDIUM = 2500


def _make_ann(ann_id: int, w: float, h: float) -> dict:
    return {"id": ann_id, "image_id": 1, "category_id": 1, "bbox": [0.0, 0.0, w, h]}


def _make_coco(annotations: list[dict]) -> dict:
    return {
        "images": [{"id": 1}],
        "categories": [{"id": 1, "name": "airplane"}],
        "annotations": annotations,
    }


@pytest.fixture
def empty_coco():
    return _make_coco([])


@pytest.fixture
def single_ann_coco():
    return _make_coco([_make_ann(1, 5.0, 5.0)])


def test_raises_when_thresholds_inverted(empty_coco):
    with pytest.raises(ValueError, match="small_threshold"):
        add_size_metadata(empty_coco, small_threshold=500, medium_threshold=100)


def test_raises_when_thresholds_equal(empty_coco):
    with pytest.raises(ValueError, match="small_threshold"):
        add_size_metadata(empty_coco, small_threshold=100, medium_threshold=100)


@pytest.mark.parametrize(
    "w, h, expected",
    [
        (5.0, 5.0, "small"),  # area=25,    below threshold
        (10.0, 10.0, "small"),  # area=100,   exactly at small threshold
        (11.0, 10.0, "medium"),  # area=110,   just above small
        (50.0, 50.0, "medium"),  # area=2500,  exactly at medium threshold
        (100.0, 100.0, "large"),  # area=10000, above medium threshold
        (7.5, 8.5, "small"),  # area=63.75, float bbox
    ],
)
def test_size_category(w, h, expected):
    ann = _make_ann(1, w, h)
    result = add_size_metadata(_make_coco([ann]), _SMALL, _MEDIUM)
    assert result["annotations"][0]["size_category"] == expected


def test_area_is_set():
    ann = _make_ann(1, 10.0, 20.0)
    result = add_size_metadata(_make_coco([ann]), _SMALL, _MEDIUM)
    assert result["annotations"][0]["area"] == pytest.approx(200.0)


def test_existing_area_is_overwritten():
    # Documents intentional behaviour: bbox area replaces any pre-existing area value
    ann = {**_make_ann(1, 10.0, 10.0), "area": 9999}
    result = add_size_metadata(_make_coco([ann]), _SMALL, _MEDIUM)
    assert result["annotations"][0]["area"] == pytest.approx(100.0)


def test_empty_annotations(empty_coco):
    result = add_size_metadata(empty_coco, _SMALL, _MEDIUM)
    assert result["annotations"] == []


def test_mutates_and_returns_same_object(single_ann_coco):
    assert add_size_metadata(single_ann_coco, _SMALL, _MEDIUM) is single_ann_coco
