from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from loguru import logger

import fiftyone as fo
from src.fiftyone._utils import (
    apply_label_filters,
    apply_sample_tag_filters,
    configure_fiftyone,
    launch_fiftyone_app,
    parse_label_filters,
)

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for dataset comparison.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Compare two dataset versions in FiftyOne")
    parser.add_argument(
        "--dataset-name",
        required=True,
        help="Name of the FiftyOne dataset",
    )
    parser.add_argument(
        "--version-a",
        required=True,
        help="First version to compare",
    )
    parser.add_argument(
        "--version-b",
        required=True,
        help="Second version to compare",
    )
    parser.add_argument(
        "--compare-by",
        choices=["filepath", "filename"],
        default="filepath",
        help=(
            "How to match images between versions. "
            "'filepath' compares full paths; 'filename' compares basename only "
            "(default: filepath)"
        ),
    )
    parser.add_argument(
        "--comparison-field",
        default="dataset_membership",
        help=(
            "Name of the Classification field to store comparison "
            "results (default: dataset_membership)"
        ),
    )
    parser.add_argument(
        "--persist",
        action="store_true",
        help="Save the comparison labels to the dataset (persisted in the database)",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Launch the FiftyOne app after comparison",
    )
    parser.add_argument(
        "--output-json",
        type=str,
        default=None,
        help="Path to save comparison results as JSON",
    )
    parser.add_argument(
        "--include-labels-a",
        nargs="+",
        required=False,
        help="Include only version A samples with any of these KEY=VALUE labels",
    )
    parser.add_argument(
        "--exclude-labels-a",
        nargs="+",
        required=False,
        help="Exclude version A samples with any of these KEY=VALUE labels",
    )
    parser.add_argument(
        "--include-labels-b",
        nargs="+",
        required=False,
        help="Include only version B samples with any of these KEY=VALUE labels",
    )
    parser.add_argument(
        "--exclude-labels-b",
        nargs="+",
        required=False,
        help="Exclude version B samples with any of these KEY=VALUE labels",
    )
    parser.add_argument(
        "--exclude-tags-a",
        nargs="+",
        required=False,
        help="Exclude version A samples carrying any of these sample-level tags",
    )
    parser.add_argument(
        "--include-tags-a",
        nargs="+",
        required=False,
        help="Include only version A samples carrying any of these sample-level tags",
    )
    parser.add_argument(
        "--exclude-tags-b",
        nargs="+",
        required=False,
        help="Exclude version B samples carrying any of these sample-level tags",
    )
    parser.add_argument(
        "--include-tags-b",
        nargs="+",
        required=False,
        help="Include only version B samples carrying any of these sample-level tags",
    )
    args = parser.parse_args()
    if not args.persist and not args.open_browser:
        parser.error("At least one of --persist or --open-browser must be set")
    return args


def _append_classification(
    sample: fo.Sample,
    comparison_field: str,
    label: str,
) -> None:
    """Append a classification label to a sample's comparison field."""
    if sample.has_field(comparison_field):
        existing = sample[comparison_field]
        if isinstance(existing, fo.Classifications):
            labels = list(cast(list, existing.classifications))
        else:
            labels = []
    else:
        labels = []
    labels.append(fo.Classification(label=label))
    sample[comparison_field] = fo.Classifications(classifications=labels)
    sample.save()


def _get_image_key(filepath: str, compare_by: str) -> str:
    """Derive the comparison key from a filepath.

    Args:
        filepath: Full image file path.
        compare_by: ``"filename"`` for basename only, otherwise full path.

    Returns:
        Key string used to match images between versions.
    """
    if compare_by == "filename":
        return Path(filepath).name
    return filepath


def compare_dataset_versions(
    dataset_name: str,
    version_a: str,
    version_b: str,
    compare_by: str = "filepath",
    comparison_field: str = "dataset_membership",
    persist: bool = False,
    include_labels_a: dict[str, list[str]] | None = None,
    exclude_labels_a: dict[str, list[str]] | None = None,
    include_labels_b: dict[str, list[str]] | None = None,
    exclude_labels_b: dict[str, list[str]] | None = None,
    exclude_tags_a: list[str] | None = None,
    include_tags_a: list[str] | None = None,
    exclude_tags_b: list[str] | None = None,
    include_tags_b: list[str] | None = None,
    open_browser: bool = False,
) -> dict[str, set[str]]:
    """Compare two versions of a dataset and label samples by membership.

    Args:
        dataset_name: Name of the FiftyOne dataset.
        version_a: First version identifier.
        version_b: Second version identifier.
        compare_by: ``"filepath"`` (full path) or ``"filename"`` (basename only).
        comparison_field: Name of the ``fo.Classification`` field for results.
        persist: If True, save labels to the dataset.
        include_labels_a: Optional include filters for version A.
        exclude_labels_a: Optional exclude filters for version A.
        include_labels_b: Optional include filters for version B.
        exclude_labels_b: Optional exclude filters for version B.
        exclude_tags_a: Sample tags whose presence should exclude a version A sample.
        include_tags_a: Sample tags whose presence should include a version A sample.
        exclude_tags_b: Sample tags whose presence should exclude a version B sample.
        include_tags_b: Sample tags whose presence should include a version B sample.
        open_browser: Launch FiftyOne app after comparison.

    Returns:
        Dict with keys ``"only_a"``, ``"only_b"``, ``"both"`` mapping to sets
        of image keys.
    """
    dataset = cast(fo.Dataset, fo.load_dataset(dataset_name))
    logger.info(f"Loaded dataset '{dataset_name}' with {dataset.count()} total samples")

    view_a = dataset.match_tags(f"v:{version_a}")
    view_b = dataset.match_tags(f"v:{version_b}")

    view_a = apply_label_filters(
        view_a, include_labels=include_labels_a, exclude_labels=exclude_labels_a
    )
    view_a = apply_sample_tag_filters(
        view_a, exclude_tags=exclude_tags_a, include_tags=include_tags_a
    )
    view_b = apply_label_filters(
        view_b, include_labels=include_labels_b, exclude_labels=exclude_labels_b
    )
    view_b = apply_sample_tag_filters(
        view_b, exclude_tags=exclude_tags_b, include_tags=include_tags_b
    )

    count_a = view_a.count()
    count_b = view_b.count()
    logger.info(f"Version '{version_a}': {count_a} samples")
    logger.info(f"Version '{version_b}': {count_b} samples")

    if count_a == 0:
        raise ValueError(f"No samples found with version '{version_a}' in dataset '{dataset_name}'")
    if count_b == 0:
        raise ValueError(f"No samples found with version '{version_b}' in dataset '{dataset_name}'")

    # Build sets of image keys per version
    keys_a: dict[str, str] = {}  # image_key -> sample_id
    for sample in view_a.iter_samples():
        key = _get_image_key(sample.filepath, compare_by)
        keys_a[key] = sample.id

    keys_b: dict[str, str] = {}
    for sample in view_b.iter_samples():
        key = _get_image_key(sample.filepath, compare_by)
        keys_b[key] = sample.id

    set_a = set(keys_a.keys())
    set_b = set(keys_b.keys())

    only_a = set_a - set_b
    only_b = set_b - set_a
    both = set_a & set_b

    label_only_a = f"{version_a}_{version_b}_only_A"
    label_only_b = f"{version_a}_{version_b}_only_B"
    label_both = f"{version_a}_{version_b}_both"

    logger.info(f"Only in version A ({version_a}):\t\t {len(only_a)} images  [{label_only_a}]")
    logger.info(f"Only in version B ({version_b}):\t\t {len(only_b)} images  [{label_only_b}]")
    logger.info(f"In both versions: \t\t\t {len(both)} images  [{label_both}]")

    if persist:
        logger.info(f"Persisting comparison labels to field '{comparison_field}'...")

        for key in only_a:
            _append_classification(
                cast(fo.Sample, dataset[keys_a[key]]), comparison_field, label_only_a
            )

        for key in both:
            _append_classification(
                cast(fo.Sample, dataset[keys_a[key]]), comparison_field, label_both
            )

        for key in only_b:
            _append_classification(
                cast(fo.Sample, dataset[keys_b[key]]), comparison_field, label_only_b
            )

        for key in both:
            _append_classification(
                cast(fo.Sample, dataset[keys_b[key]]), comparison_field, label_both
            )

        dataset.save()
        logger.info("Comparison labels saved")
    else:
        logger.info(
            "Comparison results computed but NOT persisted. "
            "Use --persist to save labels to the dataset."
        )

    if open_browser:
        view = dataset.match_tags([f"v:{version_a}", f"v:{version_b}"])
        launch_fiftyone_app(dataset, view=view)

    return {"only_a": only_a, "only_b": only_b, "both": both}


def _save_results_json(
    output_path: str,
    result: dict[str, set[str]],
    version_a: str,
    version_b: str,
    compare_by: str,
) -> None:
    """Write comparison results to a JSON file."""
    payload = {
        "version_a": version_a,
        "version_b": version_b,
        "compare_by": compare_by,
        "counts": {
            "only_a": len(result["only_a"]),
            "only_b": len(result["only_b"]),
            "both": len(result["both"]),
        },
        "only_a": sorted(result["only_a"]),
        "only_b": sorted(result["only_b"]),
        "both": sorted(result["both"]),
    }
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(payload, f, indent=2)
    logger.info(f"Comparison results saved to {output_path}")


def main() -> None:
    configure_fiftyone()
    args = _parse_args()
    result = compare_dataset_versions(
        dataset_name=args.dataset_name,
        version_a=args.version_a,
        version_b=args.version_b,
        compare_by=args.compare_by,
        comparison_field=args.comparison_field,
        persist=args.persist,
        include_labels_a=parse_label_filters(args.include_labels_a),
        exclude_labels_a=parse_label_filters(args.exclude_labels_a),
        include_labels_b=parse_label_filters(args.include_labels_b),
        exclude_labels_b=parse_label_filters(args.exclude_labels_b),
        exclude_tags_a=args.exclude_tags_a,
        include_tags_a=args.include_tags_a,
        exclude_tags_b=args.exclude_tags_b,
        include_tags_b=args.include_tags_b,
        open_browser=args.open_browser,
    )
    if args.output_json:
        _save_results_json(
            args.output_json,
            result,
            args.version_a,
            args.version_b,
            args.compare_by,
        )


if __name__ == "__main__":
    main()
