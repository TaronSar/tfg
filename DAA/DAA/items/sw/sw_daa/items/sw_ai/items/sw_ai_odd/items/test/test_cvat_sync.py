"""Unit tests for src/ood/curation/cvat_sync.py.

All tests use plain ``types.SimpleNamespace`` mocks — no FiftyOne,
no MongoDB, no CVAT network connection required.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.ood.common.config_loader import load_dataset_config
from src.ood.curation.cvat_sync import (
    CVAT_EXCLUDE_LABEL,
    EXCLUDE_TAG,
    RELABEL_TAG_PREFIX,
    RELABEL_TAG,
    _annotation_to_label,
    apply_cvat_annotations,
    push_relabel_queue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sample(cvat_relabel_value):
    """Build a minimal fake FiftyOne sample."""

    class FakeSample:
        def __init__(self, ann):
            self._ann = ann
            self.tags: list[str] = [RELABEL_TAG]

        def get_field(self, name: str):
            return self._ann if name == "cvat_relabel" else None

        def save(self):
            pass

    return FakeSample(cvat_relabel_value)


def _dataset(samples: list):
    """Build a minimal fake FiftyOne dataset."""

    class FakeDataset:
        def __init__(self, samples):
            self._samples = samples

        def load_annotations(self, anno_key, **kwargs):
            pass  # no-op in tests

        def match_tags(self, tag):
            return [s for s in self._samples if tag in s.tags]

        def save(self):
            pass

    return FakeDataset(samples)


# ---------------------------------------------------------------------------
# _annotation_to_label
# ---------------------------------------------------------------------------


class TestAnnotationToLabel:
    def test_returns_none_when_no_annotation(self):
        assert _annotation_to_label(_sample(None)) is None

    def test_reads_label_attribute(self):
        ann = SimpleNamespace(label="Urban")
        assert _annotation_to_label(_sample(ann)) == "Urban"

    def test_reads_classifications_list(self):
        ann = SimpleNamespace(classifications=[SimpleNamespace(label="Water")])
        # SimpleNamespace won't have .label unless set, so hasattr check falls through
        assert _annotation_to_label(_sample(ann)) == "Water"

    def test_empty_classifications_returns_none(self):
        ann = SimpleNamespace(classifications=[])
        assert _annotation_to_label(_sample(ann)) is None

    def test_label_attr_takes_precedence_over_classifications(self):
        ann = SimpleNamespace(label="Urban", classifications=[SimpleNamespace(label="Water")])
        assert _annotation_to_label(_sample(ann)) == "Urban"


# ---------------------------------------------------------------------------
# apply_cvat_annotations — tag mapping logic
# ---------------------------------------------------------------------------


class TestPushRelabelQueue:
    def test_no_relabel_samples_skips_annotation(self):
        class EmptyView:
            def __len__(self):
                return 0

            def annotate(self, *args, **kwargs):
                raise AssertionError("annotate() must not be called for empty view")

        class FakeDataset:
            def match_tags(self, _tag):
                return EmptyView()

        push_relabel_queue(
            FakeDataset(),
            anno_key="k",
            cvat_url="http://cvat",
            username="u",
            password="p",
            classes=["Urban", "Water"],
        )

    def test_push_calls_annotate_with_expected_schema(self):
        captured: dict = {}

        class View:
            def __len__(self):
                return 2

            def annotate(self, anno_key, **kwargs):
                captured["anno_key"] = anno_key
                captured.update(kwargs)

        class FakeDataset:
            def match_tags(self, _tag):
                return View()

        classes = ["Urban", "Non-urban", "Water", "Exclude"]
        push_relabel_queue(
            FakeDataset(),
            anno_key="round1",
            cvat_url="http://cvat",
            username="user",
            password="pass",
            classes=classes,
        )

        assert captured["anno_key"] == "round1"
        assert captured["label_schema"] == {
            "cvat_relabel": {"type": "classifications", "classes": classes}
        }
        assert captured["url"] == "http://cvat"
        assert captured["username"] == "user"
        assert captured["password"] == "pass"
        assert captured["launch_editor"] is True


class TestApplyCvatAnnotations:
    def test_exclude_label_adds_exclude_tag_and_strips_relabel(self):
        s = _sample(SimpleNamespace(label=CVAT_EXCLUDE_LABEL))
        ds = _dataset([s])
        apply_cvat_annotations(ds, "k", "http://cvat", "u", "p")
        assert EXCLUDE_TAG in s.tags
        assert RELABEL_TAG not in s.tags

    def test_exclude_label_also_strips_to_star_tags(self):
        s = _sample(SimpleNamespace(label=CVAT_EXCLUDE_LABEL))
        s.tags = [
            RELABEL_TAG,
            f"{RELABEL_TAG_PREFIX}Urban",
            f"{RELABEL_TAG_PREFIX}Water",
        ]
        ds = _dataset([s])
        apply_cvat_annotations(ds, "k", "http://cvat", "u", "p")
        relabel_tags = tuple(
            f"{RELABEL_TAG_PREFIX}{class_name}"
            for class_name in load_dataset_config()["classes"]
        )
        for to_tag in relabel_tags:
            assert to_tag not in s.tags

    def test_known_class_adds_to_tag_and_strips_relabel(self):
        for cls in load_dataset_config()["classes"]:
            s = _sample(SimpleNamespace(label=cls))
            ds = _dataset([s])
            apply_cvat_annotations(ds, "k", "http://cvat", "u", "p")
            assert f"{RELABEL_TAG_PREFIX}{cls}" in s.tags
            assert RELABEL_TAG not in s.tags

    def test_no_annotation_leaves_tags_unchanged(self):
        s = _sample(None)
        original_tags = list(s.tags)
        ds = _dataset([s])
        apply_cvat_annotations(ds, "k", "http://cvat", "u", "p")
        assert s.tags == original_tags

    def test_returns_count_of_updated_samples(self):
        samples = [
            _sample(SimpleNamespace(label="Urban")),
            _sample(SimpleNamespace(label=CVAT_EXCLUDE_LABEL)),
            _sample(None),  # no annotation — not counted
        ]
        ds = _dataset(samples)
        count = apply_cvat_annotations(ds, "k", "http://cvat", "u", "p")
        assert count == 2

    def test_exclude_not_duplicated_if_already_tagged(self):
        s = _sample(SimpleNamespace(label=CVAT_EXCLUDE_LABEL))
        s.tags = [RELABEL_TAG, EXCLUDE_TAG]
        ds = _dataset([s])
        apply_cvat_annotations(ds, "k", "http://cvat", "u", "p")
        assert s.tags.count(EXCLUDE_TAG) == 1

    def test_to_tag_not_duplicated_if_already_present(self):
        s = _sample(SimpleNamespace(label="Urban"))
        s.tags = [RELABEL_TAG, f"{RELABEL_TAG_PREFIX}Urban"]
        ds = _dataset([s])
        apply_cvat_annotations(ds, "k", "http://cvat", "u", "p")
        assert s.tags.count(f"{RELABEL_TAG_PREFIX}Urban") == 1
