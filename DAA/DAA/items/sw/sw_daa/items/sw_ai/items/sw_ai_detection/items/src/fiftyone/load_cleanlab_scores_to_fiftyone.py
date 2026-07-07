from __future__ import annotations

import argparse
import json
from pathlib import Path, PurePosixPath

from dotenv import load_dotenv
from loguru import logger

import fiftyone as fo
from src.fiftyone._utils import (
    apply_label_filters,
    configure_fiftyone,
    get_version_view,
    parse_label_filters,
)

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)

CLEANLAB_FIELD_PREFIX = "cleanlab_"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load cleanlab quality scores into a FiftyOne dataset",
    )
    parser.add_argument(
        "--dataset-name",
        required=True,
        help="Name of the existing FiftyOne dataset",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Dataset version tag to match samples",
    )
    parser.add_argument(
        "--report-path",
        required=True,
        help="Path to the cleanlab JSON report",
    )
    parser.add_argument(
        "--score-field",
        required=True,
        help="Fiftyone Sub-field name stored under the 'cleanlab_scores' group",
    )
    parser.add_argument(
        "--images-dir",
        required=True,
        help="Root directory for images (used to resolve report file_name → FiftyOne filepath)",
    )
    parser.add_argument(
        "--include-labels",
        nargs="*",
        default=None,
        help="Keep only samples matching KEY=VALUE classification labels (e.g. split=train)",
    )
    return parser.parse_args()


def _build_sample_lookup(
    version_view: fo.DatasetView,
) -> dict[str, str]:
    """Map FiftyOne filepath to sample ID for all samples in the view."""
    filepaths = version_view.values("filepath")
    sample_ids = version_view.values("id")
    return dict(zip(filepaths, sample_ids, strict=True))


def _load_report(report_path: str) -> dict:
    """Load and validate the cleanlab JSON report."""
    with open(report_path) as f:
        report = json.load(f)
    logger.info(f"Loaded report: {report['num_issues']}/{report['num_images']} issues")
    return report


def _apply_scores(
    dataset: fo.Dataset,
    filepath_lookup: dict[str, str],
    report: dict,
    images_dir: str,
    score_field: str,
) -> tuple[int, int]:
    """Write quality scores to matching samples under the ``Cleanlab Scores`` group.

    Scores are stored as flat FloatFields with the ``cleanlab_`` prefix
    (e.g. ``cleanlab_quality_score``), so all cleanlab scores are naturally
    grouped by prefix in the FiftyOne UI.

    Args:
        dataset: FiftyOne dataset to update
        filepath_lookup: Maps FiftyOne filepaths to sample IDs
        report: Cleanlab report dict
        images_dir: Root directory for images (used to resolve report file_name - FiftyOne filepath)
        score_field: Field name (``cleanlab_`` prefix added automatically).

    Returns:
        matched, unmatched
    """
    base = PurePosixPath(images_dir)

    score_field = f"{CLEANLAB_FIELD_PREFIX}{score_field}"
    if not dataset.has_sample_field(score_field):
        dataset.add_sample_field(score_field, fo.FloatField)
        logger.info(f"Created field '{score_field}'")

    scores_by_id: dict[str, float] = {}
    unmatched = 0

    for entry in report["images"]:
        full_path = str(base / entry["file_name"])
        sample_id = filepath_lookup.get(full_path)
        if sample_id is None:
            unmatched += 1
            continue

        scores_by_id[sample_id] = entry["quality_score"]

    if scores_by_id:
        dataset.set_values(score_field, scores_by_id, key_field="id")

    return len(scores_by_id), unmatched


def load_cleanlab_scores(
    dataset_name: str,
    version: str,
    report_path: str,
    images_dir: str,
    score_field: str,
    include_labels: list[str] | None = None,
) -> fo.Dataset:
    """Load cleanlab scores into a FiftyOne dataset.

    Args:
        dataset_name: Name of the existing FiftyOne dataset.
        version: Only update samples with this version tag.
        report_path: Path to the cleanlab JSON report.
        images_dir: Root directory for images (resolves report file_name → FiftyOne filepath).
        score_field: Field name for the score (``cleanlab_`` prefix added automatically).
        include_labels: KEY=VALUE classification filters to narrow the view (e.g. ["split=train"]).

    Returns:
        The updated FiftyOne dataset.
    """
    report = _load_report(report_path)
    dataset, version_view = get_version_view(dataset_name, version)
    parsed_labels = parse_label_filters(include_labels)
    if parsed_labels:
        version_view = apply_label_filters(version_view, include_labels=parsed_labels)
        logger.info(f"Applied label filters: {parsed_labels}")
    filepath_lookup = _build_sample_lookup(version_view)

    matched, unmatched = _apply_scores(
        dataset,
        filepath_lookup,
        report,
        images_dir,
        score_field,
    )

    logger.info(f"Updated {matched} samples, {unmatched} file_names not found in dataset")
    return dataset


def main() -> None:
    configure_fiftyone()
    args = _parse_args()
    load_cleanlab_scores(
        dataset_name=args.dataset_name,
        version=args.version,
        report_path=args.report_path,
        images_dir=args.images_dir,
        score_field=args.score_field,
        include_labels=args.include_labels,
    )


if __name__ == "__main__":
    main()
