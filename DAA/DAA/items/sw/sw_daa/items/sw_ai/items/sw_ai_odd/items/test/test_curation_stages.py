"""Unit tests for staged curation helpers (03b/03c/03d)."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.ood.curation.annotation_stage import (
    assert_annotation_run_complete,
    build_annotations_rows,
)
from src.ood.curation.cvat_sync import RELABEL_TAG
from src.ood.curation.queue_stage import build_queue_rows, validate_queue_nonempty


class FakeSample:
    def __init__(self, sample_id: str, filename: str, label: str, tags: list[str], split: str = "train"):
        self.id = sample_id
        self.filepath = f"/tmp/{filename}"
        self.tags = tags
        self._split = split
        self._label = label

    def get_field(self, name: str):
        if name == "split":
            return self._split
        return None

    def __getitem__(self, key: str):
        if key == "label":
            return SimpleNamespace(label=self._label)
        raise KeyError(key)


class FakeDataset:
    def __init__(self, samples: list[FakeSample], run_status: str = "complete"):
        self._samples = samples
        self._run_status = run_status

    def match_tags(self, tag: str):
        return [s for s in self._samples if tag in s.tags]

    def list_annotation_runs(self):
        return ["relabel_round1"]

    def get_annotation_info(self, run_key: str):
        return SimpleNamespace(config=SimpleNamespace(status=self._run_status))

    def __iter__(self):
        return iter(self._samples)


class TestQueueStage:
    def test_build_queue_rows_includes_only_relabel(self):
        ds = FakeDataset(
            [
                FakeSample("1", "a.jpg", "Urban", [RELABEL_TAG]),
                FakeSample("2", "b.jpg", "Urban", ["to_Water"]),
            ]
        )
        # Simulate pre-filtered view (as done in export_cvat_queue.py)
        filtered = ds.match_tags(RELABEL_TAG)
        rows = build_queue_rows(filtered, "relabel_round1")
        assert len(rows) == 1
        assert rows[0]["sample_id"] == "1"
        assert rows[0]["filename"] == "a.jpg"
        assert rows[0]["anno_key"] == "relabel_round1"
        # Verify minimal fields only (no filepath, split, label, tags, exported_at)
        assert set(rows[0].keys()) == {"sample_id", "filename", "anno_key"}

    def test_validate_queue_nonempty_raises_on_empty(self):
        with pytest.raises(ValueError):
            validate_queue_nonempty([])

    def test_validate_queue_nonempty_allows_empty_when_enabled(self):
        assert validate_queue_nonempty([], allow_empty=True) is False

    def test_validate_queue_nonempty_returns_true_when_not_empty(self):
        assert validate_queue_nonempty([{"sample_id": "1"}], allow_empty=True) is True


class TestEmptyQueueWorkflow:
    """Test handling of empty CVAT queue as no-op."""

    def test_empty_queue_export_validation_ok_with_allow_empty(self):
        """Empty queue is allowed when allow_empty=True."""
        assert validate_queue_nonempty([], allow_empty=True) is False

    def test_empty_queue_export_validation_fails_with_allow_empty_false(self):
        """Empty queue raises ValueError when allow_empty=False."""
        with pytest.raises(ValueError):
            validate_queue_nonempty([], allow_empty=False)

    def test_empty_queue_causes_pull_to_skip_gracefully(self):
        """Empty queue artifact causes pull to write empty annotations no-op."""
        queue_rows: list[dict] = []
        ds = FakeDataset([])
        # empty queue → no samples to iterate
        rows = build_annotations_rows(ds, queue_rows, "relabel_round1")
        assert rows == []

    def test_multiple_to_tags_on_same_sample_resolves_first(self):
        """Sample with multiple to_* tags resolves to first in sorted order."""
        # Annotation stage helper: when multiple to_* tags exist, takes first sorted
        s = FakeSample("1", "a.jpg", "Urban", [RELABEL_TAG, "to_Urban", "to_Water"])
        ds = FakeDataset([s])
        queue_rows = [{"sample_id": "1", "filename": "a.jpg"}]
        rows = build_annotations_rows(ds, queue_rows, "r1")
        # sorted(["to_Urban", "to_Water"])[0] = "to_Urban" → relabel = "Urban"
        assert rows[0]["resolved_relabel"] == "Urban"
        assert rows[0]["resolved_action"] == "relabel"


class TestAnnotationStage:
    def test_assert_annotation_run_complete_ok(self):
        ds = FakeDataset([])
        # skip_check=True bypasses the interactive prompt
        assert_annotation_run_complete(ds, "relabel_round1", skip_check=True)

    def test_assert_annotation_run_complete_fails_when_run_missing(self):
        ds = FakeDataset([])
        with pytest.raises(ValueError):
            assert_annotation_run_complete(ds, "nonexistent_run", skip_check=True)

    def test_assert_annotation_run_complete_fails_on_user_no(self, monkeypatch):
        ds = FakeDataset([])
        monkeypatch.setattr("sys.stdin", type("FakeTTY", (), {"isatty": lambda self: True})())
        monkeypatch.setattr("builtins.input", lambda _prompt: "no")
        with pytest.raises(ValueError):
            assert_annotation_run_complete(ds, "relabel_round1")

    def test_build_annotations_rows_maps_exclude_and_relabel(self):
        ds = FakeDataset(
            [
                FakeSample("1", "a.jpg", "Urban", ["exclude"]),
                FakeSample("2", "b.jpg", "Urban", ["to_Non-urban"]),
                FakeSample("3", "c.jpg", "Urban", [RELABEL_TAG]),
            ]
        )
        queue_rows = [
            {"sample_id": "1", "filename": "a.jpg"},
            {"sample_id": "2", "filename": "b.jpg"},
            {"sample_id": "3", "filename": "c.jpg"},
        ]
        rows = build_annotations_rows(ds, queue_rows, "relabel_round1")
        by_id = {r["sample_id"]: r for r in rows}

        assert by_id["1"]["resolved_action"] == "exclude"
        assert by_id["1"]["resolved_relabel"] is None
        assert by_id["2"]["resolved_action"] == "relabel"
        assert by_id["2"]["resolved_relabel"] == "Non-urban"
        assert by_id["3"]["resolved_action"] is None
        assert by_id["3"]["resolved_relabel"] is None

    def test_pull_with_missing_sample_skips_gracefully(self):
        """Queue references sample ID not in dataset → row skipped."""
        ds = FakeDataset([FakeSample("1", "a.jpg", "Urban", ["to_Urban"])])
        queue_rows = [
            {"sample_id": "1", "filename": "a.jpg"},
            {"sample_id": "999", "filename": "missing.jpg"},  # doesn't exist
        ]
        rows = build_annotations_rows(ds, queue_rows, "r1")
        # Only row for existing sample should be in output
        assert len(rows) == 1
        assert rows[0]["sample_id"] == "1"

    def test_pull_preserves_tags_list_in_output(self):
        """Pulled annotations row includes full tags list for audit trail."""
        s = FakeSample("1", "a.jpg", "Urban", ["to_Water", "custom_tag"])
        ds = FakeDataset([s])
        queue_rows = [{"sample_id": "1", "filename": "a.jpg"}]
        rows = build_annotations_rows(ds, queue_rows, "r1")
        assert rows[0]["tags"] == ["to_Water", "custom_tag"]
