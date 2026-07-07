from __future__ import annotations

from unittest.mock import MagicMock


def make_mock_sample(
    filepath: str = "/images/video1/frame_001.jpg",
    sample_id: str = "abc123",
    version_label: str = "v1",
) -> MagicMock:
    """Create a lightweight FiftyOne-like mock sample.

    Args:
        filepath: Sample file path.
        sample_id: Unique sample ID.
        version_label: Value for ``sample.version.label``.

    Returns:
        A ``MagicMock`` with ``.filepath``, ``.id``, and ``.version.label``.
    """
    sample = MagicMock()
    sample.filepath = filepath
    sample.id = sample_id
    sample.version = MagicMock(label=version_label)
    return sample


def make_mock_view(samples: list[MagicMock]) -> MagicMock:
    """Create a mock FiftyOne DatasetView.

    Args:
        samples: List of mock samples the view should yield.

    Returns:
        A ``MagicMock`` with ``.count()`` and ``.iter_samples()``.
    """
    view = MagicMock()
    view.count.return_value = len(samples)
    view.iter_samples.return_value = iter(samples)
    return view


def make_mock_dataset(samples: list[MagicMock]) -> MagicMock:
    """Create a mock FiftyOne Dataset.

    Args:
        samples: List of mock samples contained in the dataset.

    Returns:
        A ``MagicMock`` with ``.count()``, ``.match()``, and ``__getitem__``.
    """
    dataset = MagicMock()
    dataset.count.return_value = len(samples)
    dataset.match.return_value = make_mock_view(samples)

    all_samples = {sample.id: sample for sample in samples}
    dataset.__getitem__.side_effect = all_samples.__getitem__

    return dataset
