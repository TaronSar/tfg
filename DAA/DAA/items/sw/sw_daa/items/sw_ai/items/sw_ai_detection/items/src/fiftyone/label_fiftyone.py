from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, cast

from dotenv import load_dotenv
from loguru import logger

import fiftyone as fo
from fiftyone import ViewField as F
from src.fiftyone._filters import (
    _OPERATORS,
    _build_filter_expr,
    _cast_value,
    _parse_field_path,
    _parse_filter,
)
from src.fiftyone._utils import (
    apply_label_filters,
    apply_sample_tag_filters,
    configure_fiftyone,
    parse_label_filters,
)

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the labelling script.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Tag images or annotations in a FiftyOne dataset based on field conditions"
    )
    parser.add_argument("--dataset-name", required=True, help="Name of the FiftyOne dataset")
    parser.add_argument(
        "--version",
        required=True,
        help="Filter samples by version field before tagging.",
    )
    parser.add_argument(
        "--mode",
        choices=["sample", "detection", "add-version"],
        required=True,
        help=(
            "Tagging mode. "
            "'sample' tags entire images whose detections satisfy the condition. "
            "'detection' tags individual detections that satisfy the condition. "
            "'add-version' adds --tag as a new version label to matching samples."
        ),
    )
    parser.add_argument(
        "--tag",
        required=True,
        help=(
            "Tag string to apply (e.g. 'exclude_range_2000'), "
            "or new version label for add-version mode."
        ),
    )
    parser.add_argument(
        "--filters",
        nargs="+",
        default=None,
        metavar="FIELD:OP:VALUE",
        help=(
            "One or more filter expressions in FIELD:OPERATOR:VALUE format. "
            "Multiple filters are combined with AND logic. "
            f"Operators: {', '.join(sorted(_OPERATORS.keys()))}. "
            'Example: "ground_truth.detections.range_m:>:2000"'
        ),
    )

    parser.add_argument(
        "--include-labels",
        nargs="+",
        required=False,
        help="Include only samples that have any of these labels.",
    )
    parser.add_argument(
        "--exclude-labels",
        nargs="+",
        required=False,
        help="Exclude samples that have any of these labels.",
    )
    parser.add_argument(
        "--exclude-tags",
        nargs="+",
        required=False,
        help="Exclude samples that carry any of these sample-level tags.",
    )
    parser.add_argument(
        "--include-tags",
        nargs="+",
        required=False,
        help="Include only samples that carry any of these sample-level tags.",
    )

    return parser.parse_args()


def label_fiftyone(
    dataset_name: str,
    version: str,
    mode: str,
    tag: str,
    filters: list[str] | None = None,
    include_labels: dict[str, list[str]] | None = None,
    exclude_labels: dict[str, list[str]] | None = None,
    exclude_tags: list[str] | None = None,
    include_tags: list[str] | None = None,
) -> int:
    """Tag images or detections in a FiftyOne dataset based on field conditions.

    Args:
        dataset_name: FiftyOne dataset name.
        version: Version string to filter samples by.
        mode: ``"sample"`` to tag images, ``"detection"`` to tag detections,
            ``"add-version"`` to add ``tag`` as a new version label.
        tag: Tag string to apply, or new version label for ``add-version`` mode.
        filters: List of ``FIELD:OPERATOR:VALUE`` strings.  All conditions
            are combined with AND logic.  Optional for ``add-version`` mode.
        include_labels: Pre-filter: include only these classification labels.
        exclude_labels: Pre-filter: exclude these classification labels.
        exclude_tags: Pre-filter: exclude samples with these tags.
        include_tags: Pre-filter: include only samples with these tags.

    Returns:
        Number of items tagged.
    """
    dataset = cast(fo.Dataset, fo.load_dataset(name=dataset_name))

    view: Any = dataset.match_tags(f"v:{version}")
    n_version = view.count()
    if n_version == 0:
        logger.error(f"No samples with version '{version}' in dataset '{dataset_name}'")
        return 0
    logger.info(f"Filtered to {n_version} samples with version '{version}'")

    view = apply_label_filters(view, include_labels, exclude_labels)
    view = apply_sample_tag_filters(view, exclude_tags, include_tags)
    logger.info(f"{view.count()} samples after pre-filtering")

    if mode == "add-version":
        needs_tag = view.match(~F("tags").contains(f"v:{tag}"))
        count = needs_tag.count()
        if count == 0:
            logger.warning("All matching samples already have this version")
            return 0

        logger.info(f"Adding version '{tag}' to {count} samples...")
        needs_tag.tag_samples(f"v:{tag}")
        logger.info(f"Added version '{tag}' to {count} samples")
        return count

    if not filters:
        raise ValueError("--filters is required for 'sample' and 'detection' modes")

    parsed: list[tuple[str | None, Any]] = []
    for raw in filters:
        field, op, value_str = _parse_filter(raw)
        label_field, leaf = _parse_field_path(field)
        parsed.append((label_field, _build_filter_expr(leaf, op, _cast_value(value_str))))

    filter_desc = " AND ".join(filters)

    if mode == "sample":
        for label_field, expr in parsed:
            if label_field is not None:
                view = view.match(F(f"{label_field}.detections").filter(expr).length() > 0)
            else:
                view = view.match(expr)

        count = view.count()
        logger.info(f"{count} samples match ({filter_desc})")
        if count > 0:
            view.tag_samples(tag)
            logger.info(f"Tagged {count} samples with '{tag}'")
        return count

    elif mode == "detection":
        for label_field, expr in parsed:
            if label_field is None:
                raise ValueError(
                    f"In 'detection' mode all filters must target detection attributes "
                    f"(e.g. '<field>.detections.<attr>'). Got: {filter_desc}"
                )
            view = view.filter_labels(label_field, expr)

        count = view.count()
        logger.info(f"{count} samples with matching detections ({filter_desc})")
        if count > 0:
            view.tag_labels(tag)
            logger.info(f"Tagged matching detections across {count} samples with '{tag}'")
        return count

    else:
        raise ValueError(f"Unsupported mode: {mode}")


def main() -> None:
    configure_fiftyone()
    args = _parse_args()

    label_fiftyone(
        dataset_name=args.dataset_name,
        version=args.version,
        mode=args.mode,
        tag=args.tag,
        filters=args.filters,
        include_labels=parse_label_filters(args.include_labels),
        exclude_labels=parse_label_filters(args.exclude_labels),
        exclude_tags=args.exclude_tags,
        include_tags=args.include_tags,
    )


if __name__ == "__main__":
    main()
