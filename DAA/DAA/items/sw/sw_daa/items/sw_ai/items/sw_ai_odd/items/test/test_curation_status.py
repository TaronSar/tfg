"""Unit tests for src/ood/curation/status.py.

Uses a plain Python mock dataset — no FiftyOne, no MongoDB required.
"""
from __future__ import annotations

from types import SimpleNamespace

from src.ood.curation.cvat_sync import EXCLUDE_TAG, RELABEL_TAG
from src.ood.curation.status import get_curation_status


# ---------------------------------------------------------------------------
# Mock dataset
# ---------------------------------------------------------------------------


class MockView:
    def __init__(self, n: int):
        self._n = n

    def __len__(self) -> int:
        return self._n

    def __iter__(self):
        return iter([object()] * self._n)


class MockDataset:
    """Minimal fake FiftyOne dataset for status tests."""

    def __init__(
        self,
        total: int,
        n_excluded: int,
        relabel_tag_counts: dict[str, int],
        n_relabel_queue: int,
        annotation_runs: dict[str, str],
    ):
        self._total = total
        self._n_excluded = n_excluded
        self._relabel_tag_counts = relabel_tag_counts
        self._n_relabel_queue = n_relabel_queue
        self._annotation_runs = annotation_runs

    def __len__(self) -> int:
        return self._total

    def match_tags(self, tag: str) -> MockView:
        if tag == EXCLUDE_TAG:
            return MockView(self._n_excluded)
        if tag == RELABEL_TAG:
            return MockView(self._n_relabel_queue)
        return MockView(self._relabel_tag_counts.get(tag, 0))

    def list_annotation_runs(self) -> list[str]:
        return list(self._annotation_runs.keys())

    def get_annotation_info(self, run_key: str):
        status_val = self._annotation_runs[run_key]
        return SimpleNamespace(config=SimpleNamespace(status=status_val))

    def load_annotations(self, anno_key: str, **kwargs):
        _ = (anno_key, kwargs)

    def save(self):
        return None

    def __iter__(self):
        return iter(())


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestGetCurationStatus:
    def test_empty_dataset(self):
        ds = MockDataset(0, 0, {}, 0, {})
        s = get_curation_status(ds)
        assert s["total"] == 0
        assert s["n_excluded"] == 0
        assert s["n_relabeled"] == 0
        assert s["relabel_counts"] == {}
        assert s["n_relabel_queue"] == 0
        assert s["pending_runs"] == []

    def test_excluded_count(self):
        ds = MockDataset(100, 15, {}, 0, {})
        s = get_curation_status(ds)
        assert s["n_excluded"] == 15

    def test_relabel_tag_counts_summed(self):
        relabel_tag_counts = {"to_Urban": 5, "to_Water": 3}
        ds = MockDataset(100, 0, relabel_tag_counts, 0, {})
        s = get_curation_status(ds)
        assert s["n_relabeled"] == 8
        assert s["relabel_counts"]["to_Urban"] == 5
        assert s["relabel_counts"]["to_Water"] == 3

    def test_zero_count_tags_excluded_from_relabel_counts(self):
        ds = MockDataset(100, 0, {"to_Urban": 2}, 0, {})
        s = get_curation_status(ds)
        assert "to_Non-urban" not in s["relabel_counts"]
        assert "to_Water" not in s["relabel_counts"]

    def test_relabel_queue_count(self):
        ds = MockDataset(100, 0, {}, 7, {})
        s = get_curation_status(ds)
        assert s["n_relabel_queue"] == 7

    def test_pending_runs_only_incomplete(self):
        ds = MockDataset(
            100, 0, {}, 0,
            {"relabel_round1": "in_progress", "relabel_round2": "complete"},
        )
        s = get_curation_status(ds)
        assert "relabel_round1" in s["pending_runs"]
        assert "relabel_round2" not in s["pending_runs"]

    def test_no_annotation_runs(self):
        ds = MockDataset(50, 0, {}, 0, {})
        s = get_curation_status(ds)
        assert s["pending_runs"] == []

    def test_all_runs_complete_returns_empty_pending(self):
        ds = MockDataset(50, 0, {}, 0, {"r1": "complete", "r2": "complete"})
        s = get_curation_status(ds)
        assert s["pending_runs"] == []

    def test_total_minus_excluded_reflects_training_set_size(self):
        ds = MockDataset(200, 30, {}, 0, {})
        s = get_curation_status(ds)
        assert s["total"] - s["n_excluded"] == 170
