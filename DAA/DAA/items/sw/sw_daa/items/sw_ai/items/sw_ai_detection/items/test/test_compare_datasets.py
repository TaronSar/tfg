import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

import fiftyone

if not hasattr(fiftyone, "ViewField"):
    fiftyone.ViewField = MagicMock()
if not hasattr(fiftyone, "config"):
    fiftyone.config = SimpleNamespace(database_uri=None)


from test._fiftyone_mocks import (
    make_mock_sample as _make_sample,
)
from test._fiftyone_mocks import (
    make_mock_view as _make_view,
)


@pytest.fixture(autouse=True)
def patch_fo(monkeypatch):
    """Prevent any real FiftyOne / MongoDB connection."""
    fake_fo = SimpleNamespace(
        config=SimpleNamespace(database_uri=None),
    )
    monkeypatch.setattr("src.fiftyone.compare_datasets.fo", fake_fo)


class TestGetImageKey:
    def test_filepath_mode_returns_full_path(self):
        from src.fiftyone.compare_datasets import _get_image_key

        assert _get_image_key("/data/images/frame.jpg", "filepath") == "/data/images/frame.jpg"

    def test_filename_mode_returns_basename(self):
        from src.fiftyone.compare_datasets import _get_image_key

        assert _get_image_key("/data/images/frame.jpg", "filename") == "frame.jpg"

    def test_filename_mode_nested_path(self):
        from src.fiftyone.compare_datasets import _get_image_key

        assert _get_image_key("/a/b/c/d/img.png", "filename") == "img.png"


class TestParseArgs:
    def test_parses_dataset_name(self):
        from src.fiftyone.compare_datasets import _parse_args

        argv = [
            "compare_datasets.py",
            "--dataset-name",
            "dataset_name",
            "--version-a",
            "v1",
            "--version-b",
            "v2",
            "--persist",
        ]
        with patch("sys.argv", argv):
            args = _parse_args()

        assert args.dataset_name == "dataset_name"

    def test_parses_include_exclude_filters_for_a_and_b(self):
        from src.fiftyone.compare_datasets import _parse_args

        argv = [
            "compare_datasets.py",
            "--dataset-name",
            "dataset_name",
            "--version-a",
            "v1",
            "--version-b",
            "v2",
            "--include-labels-a",
            "split=train",
            "source=manual",
            "--exclude-labels-a",
            "status=excluded",
            "--include-labels-b",
            "split=eval",
            "--exclude-labels-b",
            "status=noisy",
            "--open-browser",
        ]
        with patch("sys.argv", argv):
            args = _parse_args()

        assert args.include_labels_a == ["split=train", "source=manual"]
        assert args.exclude_labels_a == ["status=excluded"]
        assert args.include_labels_b == ["split=eval"]
        assert args.exclude_labels_b == ["status=noisy"]

    def test_error_when_neither_persist_nor_open_browser(self):
        from src.fiftyone.compare_datasets import _parse_args

        argv = [
            "compare_datasets.py",
            "--dataset-name",
            "ds",
            "--version-a",
            "v1",
            "--version-b",
            "v2",
        ]
        with patch("sys.argv", argv), pytest.raises(SystemExit):
            _parse_args()


class TestParseLabelFilters:
    def test_groups_values_by_key(self):
        from src.fiftyone._utils import parse_label_filters

        result = parse_label_filters(["split=train", "split=eval", "source=manual"])

        assert result == {
            "split": ["train", "eval"],
            "source": ["manual"],
        }

    def test_invalid_label_filter_raises(self):
        from src.fiftyone._utils import parse_label_filters

        with pytest.raises(ValueError, match="Invalid label format"):
            parse_label_filters(["split-train"])


class TestCompareDatasetVersions:
    def _run(self, samples_a, samples_b, **kwargs):
        from src.fiftyone.compare_datasets import compare_dataset_versions

        dataset = MagicMock()
        dataset.count.return_value = len(samples_a) + len(samples_b)
        dataset.match_tags.side_effect = [_make_view(samples_a), _make_view(samples_b)]

        all_samples = {sample.id: sample for sample in samples_a + samples_b}
        dataset.__getitem__.side_effect = all_samples.__getitem__

        with patch("src.fiftyone.compare_datasets.fo") as mock_fo:
            mock_fo.load_dataset.return_value = dataset
            mock_fo.Classification = MagicMock
            mock_fo.Classifications = MagicMock
            result = compare_dataset_versions(
                dataset_name="dataset_name",
                version_a="v1",
                version_b="v2",
                **kwargs,
            )
        return result, dataset

    def test_disjoint_sets(self):
        sa = [_make_sample(filepath="/img/a.jpg", sample_id="1")]
        sb = [_make_sample(filepath="/img/b.jpg", sample_id="2")]
        result, _ = self._run(sa, sb)

        assert result["only_a"] == {"/img/a.jpg"}
        assert result["only_b"] == {"/img/b.jpg"}
        assert result["both"] == set()

    def test_identical_sets(self):
        sa = [_make_sample(filepath="/img/x.jpg", sample_id="1")]
        sb = [_make_sample(filepath="/img/x.jpg", sample_id="2")]
        result, _ = self._run(sa, sb)

        assert result["only_a"] == set()
        assert result["only_b"] == set()
        assert result["both"] == {"/img/x.jpg"}

    def test_overlap(self):
        sa = [
            _make_sample(filepath="/img/a.jpg", sample_id="1"),
            _make_sample(filepath="/img/shared.jpg", sample_id="2"),
        ]
        sb = [
            _make_sample(filepath="/img/b.jpg", sample_id="3"),
            _make_sample(filepath="/img/shared.jpg", sample_id="4"),
        ]
        result, _ = self._run(sa, sb)

        assert result["only_a"] == {"/img/a.jpg"}
        assert result["only_b"] == {"/img/b.jpg"}
        assert result["both"] == {"/img/shared.jpg"}

    def test_compare_by_filename(self):
        sa = [_make_sample(filepath="/dir1/frame.jpg", sample_id="1")]
        sb = [_make_sample(filepath="/dir2/frame.jpg", sample_id="2")]
        result, _ = self._run(sa, sb, compare_by="filename")

        assert result["both"] == {"frame.jpg"}
        assert result["only_a"] == set()
        assert result["only_b"] == set()

    def test_compare_by_filepath_different_dirs(self):
        sa = [_make_sample(filepath="/dir1/frame.jpg", sample_id="1")]
        sb = [_make_sample(filepath="/dir2/frame.jpg", sample_id="2")]
        result, _ = self._run(sa, sb, compare_by="filepath")

        assert result["only_a"] == {"/dir1/frame.jpg"}
        assert result["only_b"] == {"/dir2/frame.jpg"}
        assert result["both"] == set()

    def test_empty_version_a_raises(self):
        from src.fiftyone.compare_datasets import compare_dataset_versions

        dataset = MagicMock()
        empty_view = _make_view([])
        non_empty_view = _make_view([_make_sample()])
        dataset.match_tags.side_effect = [empty_view, non_empty_view]

        with patch("src.fiftyone.compare_datasets.fo") as mock_fo:
            mock_fo.load_dataset.return_value = dataset
            with pytest.raises(ValueError, match="No samples found with version 'v1'"):
                compare_dataset_versions(
                    dataset_name="test_ds",
                    version_a="v1",
                    version_b="v2",
                )

    def test_empty_version_b_raises(self):
        from src.fiftyone.compare_datasets import compare_dataset_versions

        dataset = MagicMock()
        non_empty_view = _make_view([_make_sample()])
        empty_view = _make_view([])
        dataset.match_tags.side_effect = [non_empty_view, empty_view]

        with patch("src.fiftyone.compare_datasets.fo") as mock_fo:
            mock_fo.load_dataset.return_value = dataset
            with pytest.raises(ValueError, match="No samples found with version 'v2'"):
                compare_dataset_versions(
                    dataset_name="test_ds",
                    version_a="v1",
                    version_b="v2",
                )

    def test_persist_saves_labels(self):
        sa = [_make_sample(filepath="/img/a.jpg", sample_id="1")]
        sb = [_make_sample(filepath="/img/b.jpg", sample_id="2")]
        _, dataset = self._run(sa, sb, persist=True)

        dataset.save.assert_called_once()

    def test_applies_separate_filters_to_a_and_b(self):
        from src.fiftyone.compare_datasets import compare_dataset_versions

        dataset = MagicMock()
        dataset.count.return_value = 4

        sample_a = _make_sample(filepath="/img/raw_a.jpg", sample_id="1")
        sample_b = _make_sample(filepath="/img/raw_b.jpg", sample_id="2")
        sample_fa = _make_sample(filepath="/img/filtered_a.jpg", sample_id="3")
        sample_fb = _make_sample(filepath="/img/filtered_b.jpg", sample_id="4")

        view_a = _make_view([sample_a])
        view_b = _make_view([sample_b])
        filtered_a = _make_view([sample_fa])
        filtered_b = _make_view([sample_fb])
        dataset.match_tags.side_effect = [view_a, view_b]

        all_samples = {s.id: s for s in [sample_a, sample_b, sample_fa, sample_fb]}
        dataset.__getitem__.side_effect = all_samples.__getitem__

        with patch("src.fiftyone.compare_datasets.fo") as mock_fo:
            mock_fo.load_dataset.return_value = dataset
            with patch(
                "src.fiftyone.compare_datasets.apply_label_filters",
                side_effect=[filtered_a, filtered_b],
            ) as mock_apply_filters:
                result = compare_dataset_versions(
                    dataset_name="dataset_name",
                    version_a="v1",
                    version_b="v2",
                    include_labels_a={"split": ["train"]},
                    exclude_labels_a={"status": ["excluded"]},
                    include_labels_b={"split": ["eval"]},
                    exclude_labels_b={"status": ["noisy"]},
                )

        assert result["only_a"] == {"/img/filtered_a.jpg"}
        assert result["only_b"] == {"/img/filtered_b.jpg"}
        assert result["both"] == set()
        assert mock_apply_filters.call_count == 2
        assert mock_apply_filters.call_args_list[0].kwargs == {
            "include_labels": {"split": ["train"]},
            "exclude_labels": {"status": ["excluded"]},
        }
        assert mock_apply_filters.call_args_list[1].kwargs == {
            "include_labels": {"split": ["eval"]},
            "exclude_labels": {"status": ["noisy"]},
        }

    def test_counts_add_up(self):
        sa = [_make_sample(filepath=f"/img/{i}.jpg", sample_id=str(i)) for i in range(5)]
        sb = [_make_sample(filepath=f"/img/{i}.jpg", sample_id=str(i + 10)) for i in range(3, 8)]
        result, _ = self._run(sa, sb)

        assert len(result["only_a"]) + len(result["only_b"]) + len(result["both"]) == len(
            set(s.filepath for s in sa) | set(s.filepath for s in sb)
        )


class TestSaveResultsJson:
    def test_output_file_created(self, tmp_path):
        from src.fiftyone.compare_datasets import _save_results_json

        out = tmp_path / "results.json"
        _save_results_json(
            str(out),
            {"only_a": {"a.jpg"}, "only_b": {"b.jpg"}, "both": {"c.jpg"}},
            "v1",
            "v2",
            "filepath",
        )
        assert out.exists()

    def test_output_is_valid_json(self, tmp_path):
        from src.fiftyone.compare_datasets import _save_results_json

        out = tmp_path / "results.json"
        _save_results_json(
            str(out),
            {"only_a": set(), "only_b": set(), "both": set()},
            "v1",
            "v2",
            "filepath",
        )
        data = json.loads(out.read_text())
        assert isinstance(data, dict)

    def test_top_level_keys(self, tmp_path):
        from src.fiftyone.compare_datasets import _save_results_json

        out = tmp_path / "results.json"
        _save_results_json(
            str(out),
            {"only_a": {"a.jpg"}, "only_b": set(), "both": {"c.jpg"}},
            "v1",
            "v2",
            "filename",
        )
        data = json.loads(out.read_text())
        assert data["version_a"] == "v1"
        assert data["version_b"] == "v2"
        assert data["compare_by"] == "filename"
        for key in ("counts", "only_a", "only_b", "both"):
            assert key in data

    def test_counts_match_lists(self, tmp_path):
        from src.fiftyone.compare_datasets import _save_results_json

        out = tmp_path / "results.json"
        result = {"only_a": {"x.jpg", "y.jpg"}, "only_b": {"z.jpg"}, "both": {"w.jpg"}}
        _save_results_json(str(out), result, "v1", "v2", "filepath")
        data = json.loads(out.read_text())

        assert data["counts"]["only_a"] == 2
        assert data["counts"]["only_b"] == 1
        assert data["counts"]["both"] == 1
        assert len(data["only_a"]) == 2
        assert len(data["only_b"]) == 1
        assert len(data["both"]) == 1

    def test_lists_are_sorted(self, tmp_path):
        from src.fiftyone.compare_datasets import _save_results_json

        out = tmp_path / "results.json"
        _save_results_json(
            str(out),
            {"only_a": {"c.jpg", "a.jpg", "b.jpg"}, "only_b": set(), "both": set()},
            "v1",
            "v2",
            "filepath",
        )
        data = json.loads(out.read_text())
        assert data["only_a"] == ["a.jpg", "b.jpg", "c.jpg"]

    def test_creates_parent_directories(self, tmp_path):
        from src.fiftyone.compare_datasets import _save_results_json

        out = tmp_path / "sub" / "dir" / "results.json"
        _save_results_json(
            str(out),
            {"only_a": set(), "only_b": set(), "both": set()},
            "v1",
            "v2",
            "filepath",
        )
        assert out.exists()

    def test_empty_result(self, tmp_path):
        from src.fiftyone.compare_datasets import _save_results_json

        out = tmp_path / "results.json"
        _save_results_json(
            str(out),
            {"only_a": set(), "only_b": set(), "both": set()},
            "v1",
            "v2",
            "filepath",
        )
        data = json.loads(out.read_text())
        assert data["counts"] == {"only_a": 0, "only_b": 0, "both": 0}
        assert data["only_a"] == []
        assert data["only_b"] == []
        assert data["both"] == []
