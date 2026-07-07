from __future__ import annotations

import os
from functools import reduce
from operator import or_
from typing import Any, cast

from loguru import logger

import fiftyone as fo
from fiftyone import ViewField as F


def _any_classification_matches(field: str, values: list[str]) -> Any:
    """ViewField expression matching samples where any classification label is in *values*."""
    return reduce(or_, (F(f"{field}.classifications.label").contains(v) for v in values))


def parse_label_filters(raw: list[str] | None) -> dict[str, list[str]]:
    """Parse ``KEY=VALUE`` pairs and group values by key.

    Args:
        raw: List of strings in ``KEY=VALUE`` format, or ``None``.

    Returns:
        Dict mapping each key to a list of values.

    Raises:
        ValueError: If an item does not contain ``=``.
    """
    if not raw:
        return {}
    result: dict[str, list[str]] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(
                f"Invalid label format: '{item}'. Expected KEY=VALUE (e.g. split=train)"
            )
        key, value = item.split("=", 1)
        result.setdefault(key, []).append(value)
    return result


def apply_sample_tag_filters(
    view: Any,
    exclude_tags: list[str] | None = None,
    include_tags: list[str] | None = None,
) -> Any:
    """Include or exclude samples that carry any of the given sample-level tags.

    Args:
        view: A FiftyOne ``DatasetView``.
        exclude_tags: Sample tags whose presence should exclude a sample.
        include_tags: Sample tags whose presence should include a sample.

    Returns:
        Filtered view.
    """
    if exclude_tags:
        view = view.match_tags(exclude_tags, bool=False)
    if include_tags:
        view = view.match_tags(include_tags, bool=True)
    return view


def apply_label_filters(
    view: Any,
    include_labels: dict[str, list[str]] | None = None,
    exclude_labels: dict[str, list[str]] | None = None,
) -> Any:
    """Apply include/exclude classification-label filters to a FiftyOne view.

    Args:
        view: A FiftyOne ``DatasetView``.
        include_labels: Keep only samples matching these ``{field: [values]}``.
        exclude_labels: Remove samples matching these ``{field: [values]}``.

    Returns:
        Filtered view.
    """
    if include_labels:
        for key, values in include_labels.items():
            view = view.match(_any_classification_matches(key, values))

    if exclude_labels:
        for key, values in exclude_labels.items():
            view = view.match(~_any_classification_matches(key, values))

    return view


def get_version_view(
    dataset_name: str,
    version: str,
) -> tuple[fo.Dataset, fo.DatasetView]:
    """Load a FiftyOne dataset and filter to samples with the given version tag.

    Args:
        dataset_name: Name of the existing FiftyOne dataset.
        version: Version number (matched as tag ``v:{version}``).

    Returns:
        ``(dataset, version_view)`` — the full dataset and the filtered view.

    Raises:
        ValueError: If no samples match the version tag.
    """
    dataset = cast(fo.Dataset, fo.load_dataset(dataset_name))
    version_view = dataset.match_tags(f"v:{version}")
    version_count = version_view.count()
    if version_count == 0:
        raise ValueError(f"No samples with version '{version}' in dataset '{dataset_name}'")

    logger.info(f"Filtered to {version_count} samples with version '{version}'")
    return dataset, version_view


def configure_fiftyone() -> None:
    """Set FiftyOne database URI from the environment.

    Call once in each script's ``main()`` before any ``fo.load_dataset`` call.
    """
    uri = os.environ.get("FIFTYONE_DATABASE_URI", "mongodb://localhost:27017")
    fo.config.database_uri = uri


def launch_fiftyone_app(
    dataset: fo.Dataset,
    view: Any | None = None,
) -> Any:
    """Launch the FiftyOne App"""
    configure_fiftyone()
    session = fo.launch_app(dataset=dataset)
    if view is not None:
        session.view = view
    return session
