"""Unit tests for apply_curation.py private helpers.

These tests exercise the pure data-transformation functions
``_build_curation_index`` and ``_apply_to_split`` in isolation — no
FiftyOne, no MongoDB, no DVC required.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Load apply_curation as a module without invoking fire at import time.
# The script guards its entry-point with ``if __name__ == "__main__"``.
# ---------------------------------------------------------------------------
_SCRIPTS = Path(__file__).parents[1] / "scripts"
_spec = importlib.util.spec_from_file_location("apply_curation", _SCRIPTS / "apply_curation.py")
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)

_build_curation_index = _mod._build_curation_index
_apply_to_split = _mod._apply_to_split


# ---------------------------------------------------------------------------
# _build_curation_index
# ---------------------------------------------------------------------------


class TestBuildCurationIndex:
    def test_exclude_flag_adds_to_exclusion_set(self):
        rows = [
            {"filename": "a.jpg", "exclude": True, "relabel": None},
            {"filename": "b.jpg", "exclude": False, "relabel": None},
        ]
        exclusions, relabels = _build_curation_index(rows)
        assert "a.jpg" in exclusions
        assert "b.jpg" not in exclusions
        assert relabels == {}

    def test_relabel_only_populates_relabel_map(self):
        rows = [{"filename": "b.jpg", "exclude": False, "relabel": "Urban"}]
        exclusions, relabels = _build_curation_index(rows)
        assert exclusions == set()
        assert relabels == {"b.jpg": "Urban"}

    def test_exclude_overrides_relabel(self):
        rows = [{"filename": "c.jpg", "exclude": True, "relabel": "Water"}]
        exclusions, relabels = _build_curation_index(rows)
        assert "c.jpg" in exclusions
        assert "c.jpg" not in relabels

    def test_empty_snapshot_returns_empty_structures(self):
        exclusions, relabels = _build_curation_index([])
        assert exclusions == set()
        assert relabels == {}

    def test_multiple_relabels_and_excludes(self):
        rows = [
            {"filename": "a.jpg", "exclude": False, "relabel": "Urban"},
            {"filename": "b.jpg", "exclude": True, "relabel": None},
            {"filename": "c.jpg", "exclude": False, "relabel": "Water"},
        ]
        exclusions, relabels = _build_curation_index(rows)
        assert exclusions == {"b.jpg"}
        assert relabels == {"a.jpg": "Urban", "c.jpg": "Water"}


# ---------------------------------------------------------------------------
# _apply_to_split
# ---------------------------------------------------------------------------


def _records(*img_names: str, label: str = "Urban") -> list[dict]:
    return [{"img_name": n, "label": label} for n in img_names]


class TestApplyToSplit:
    def test_passthrough_with_no_changes(self):
        records = _records("a.jpg", "b.jpg")
        emb = np.ones((2, 4))
        out_records, out_emb = _apply_to_split(records, emb, set(), {}, "train")
        assert len(out_records) == 2
        assert out_emb.shape == (2, 4)

    def test_excluded_sample_is_removed(self):
        records = _records("a.jpg", "b.jpg")
        emb = np.array([[1.0, 0.0], [0.0, 1.0]])
        out_records, out_emb = _apply_to_split(records, emb, {"a.jpg"}, {}, "train")
        assert len(out_records) == 1
        assert out_records[0]["img_name"] == "b.jpg"
        assert out_emb.shape == (1, 2)
        np.testing.assert_array_equal(out_emb[0], [0.0, 1.0])

    def test_relabeled_sample_has_updated_label(self):
        records = _records("a.jpg", label="Urban")
        emb = np.ones((1, 4))
        out_records, _ = _apply_to_split(records, emb, set(), {"a.jpg": "Water"}, "train")
        assert out_records[0]["label"] == "Water"

    def test_relabel_does_not_mutate_original_record(self):
        original = {"img_name": "a.jpg", "label": "Urban"}
        _, _ = _apply_to_split([original], np.ones((1, 4)), set(), {"a.jpg": "Water"}, "train")
        assert original["label"] == "Urban"

    def test_all_excluded_produces_empty_output(self):
        records = _records("a.jpg")
        emb = np.ones((1, 4))
        out_records, out_emb = _apply_to_split(records, emb, {"a.jpg"}, {}, "train")
        assert len(out_records) == 0
        assert out_emb.shape[0] == 0

    def test_ordering_preserved_after_partial_exclusion(self):
        records = _records("a.jpg", "b.jpg", "c.jpg")
        emb = np.eye(3)
        out_records, out_emb = _apply_to_split(records, emb, {"b.jpg"}, {}, "train")
        assert [r["img_name"] for r in out_records] == ["a.jpg", "c.jpg"]
        np.testing.assert_array_equal(out_emb[0], [1, 0, 0])
        np.testing.assert_array_equal(out_emb[1], [0, 0, 1])

    def test_exclusion_and_relabel_on_same_snapshot(self):
        records = _records("a.jpg", "b.jpg", "c.jpg")
        emb = np.eye(3)
        exclusions = {"b.jpg"}
        relabels = {"a.jpg": "Non-urban"}
        out_records, out_emb = _apply_to_split(records, emb, exclusions, relabels, "val")
        assert len(out_records) == 2
        assert out_records[0]["label"] == "Non-urban"
        assert out_records[1]["img_name"] == "c.jpg"
