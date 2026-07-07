from __future__ import annotations

import argparse
import copy
import time
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

import fiftyone as fo
from src.fiftyone._filters import _OPERATORS, _matches_filters, parse_detection_filters
from src.fiftyone._utils import configure_fiftyone

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Clone a FiftyOne label field and reclassify detections matching attribute filters. "
            "The source field is left untouched; the cloned field gets matching detections "
            "relabelled to a new category name."
        )
    )
    parser.add_argument("--dataset-name", required=True, help="FiftyOne dataset name")
    parser.add_argument(
        "--source-version",
        required=True,
        help="Version tag of samples to process (e.g. '10')",
    )
    parser.add_argument(
        "--source-label-field",
        default="ground_truth",
        help="Label field to clone from (default: ground_truth)",
    )
    parser.add_argument(
        "--target-label-field",
        required=True,
        help="Name of the new label field to create (e.g. 'ground_truth_v12')",
    )
    parser.add_argument(
        "--target-version",
        required=True,
        help="If provided, tag all processed samples with this version (e.g. '12')",
    )
    parser.add_argument(
        "--filters",
        nargs="+",
        required=True,
        metavar="FIELD:OP:VALUE",
        help=(
            "One or more filter expressions in FIELD:OPERATOR:VALUE format. "
            "Detections matching ALL filters get relabelled. "
            f"Operators: {', '.join(sorted(_OPERATORS.keys()))}. "
            'Example: "ground_truth.detections.bbox_area:<:200"'
        ),
    )
    parser.add_argument(
        "--new-category-name",
        required=True,
        help="Class name to assign to detections that match the filters (e.g. 'undetermined')",
    )
    parser.add_argument(
        "--override",
        action="store_true",
        help="If the target label field already exists, delete it before writing",
    )
    return parser.parse_args()


def clone_and_reclassify_labels(
    dataset_name: str,
    source_version: str,
    source_label_field: str,
    target_label_field: str,
    raw_filters: list[str],
    new_category_name: str,
    target_version: str | None = None,
    override: bool = False,
) -> int:
    """Clone a label field and reclassify detections matching attribute filters.

    Iterates over all samples tagged with ``v:{source_version}``, deep-copies
    every detection from ``source_label_field`` into ``target_label_field``,
    and changes the ``label`` of detections that match ALL ``raw_filters`` to
    ``new_category_name``.  The source field is never modified.

    Args:
        dataset_name: FiftyOne dataset name.
        source_version: Version tag used to select samples (without ``v:`` prefix).
        source_label_field: Label field to clone (e.g. ``"ground_truth"``).
        target_label_field: New label field name (e.g. ``"ground_truth_v12"``).
        raw_filters: List of ``FIELD:OPERATOR:VALUE`` strings.
        new_category_name: Label to assign to matching detections.
        target_version: If given, add ``v:{target_version}`` tag to all processed samples.
        override: If True and target field exists, delete it first.

    Returns:
        Number of detections reclassified across all samples.
    """
    dataset = cast(fo.Dataset, fo.load_dataset(dataset_name))
    logger.info(f"Loaded dataset '{dataset_name}' with {dataset.count()} samples")

    version_view = dataset.match_tags(f"v:{source_version}")
    version_count = version_view.count()
    if version_count == 0:
        raise ValueError(f"No samples with version '{source_version}' in dataset '{dataset_name}'")
    logger.info(f"Filtered to {version_count} samples with version '{source_version}'")

    if dataset.has_sample_field(target_label_field):
        if not override:
            raise ValueError(
                f"Target field '{target_label_field}' already exists. Use --override to replace it."
            )
        else:
            logger.warning(
                f"Deleting in 5 seconds existing field '{target_label_field}' (--override)"
            )
            time.sleep(5)
            dataset.delete_sample_field(target_label_field)

    logger.info(f"Filters: {raw_filters}")
    parsed_filters = parse_detection_filters(raw_filters)

    all_new_detections: list[fo.Detections | None] = []
    total_reclassified = 0

    for sample in tqdm(
        version_view.iter_samples(autosave=False),
        total=version_count,
        desc="Cloning & reclassifying",
        unit="sample",
    ):
        source_field = sample.get_field(source_label_field)
        if source_field is None or not hasattr(source_field, "detections"):
            all_new_detections.append(None)
            continue

        new_dets = []
        for det in source_field.detections:
            cloned = copy.deepcopy(det)
            if _matches_filters(cloned, parsed_filters):
                cloned.label = new_category_name
                total_reclassified += 1
            new_dets.append(cloned)

        all_new_detections.append(fo.Detections(detections=new_dets))

    logger.info(f"Writing '{target_label_field}' field to {version_count} samples...")
    version_view.set_values(target_label_field, all_new_detections)

    if target_version is not None:
        needs_tag = version_view.match(~fo.ViewField("tags").contains(f"v:{target_version}"))
        tag_count = needs_tag.count()
        if tag_count > 0:
            needs_tag.tag_samples(f"v:{target_version}")
            logger.info(f"Tagged {tag_count} samples with 'v:{target_version}'")

    if new_category_name not in (dataset.default_classes or []):
        dataset.default_classes = list(dataset.default_classes or []) + [new_category_name]

    dataset.add_dynamic_sample_fields()
    dataset.save()

    logger.info(
        f"Done. Reclassified {total_reclassified} detections -> '{new_category_name}' "
        f"in field '{target_label_field}'"
    )
    return total_reclassified


def main() -> None:
    configure_fiftyone()
    args = _parse_args()
    clone_and_reclassify_labels(
        dataset_name=args.dataset_name,
        source_version=args.source_version,
        source_label_field=args.source_label_field,
        target_label_field=args.target_label_field,
        raw_filters=args.filters,
        new_category_name=args.new_category_name,
        target_version=args.target_version,
        override=args.override,
    )


if __name__ == "__main__":
    main()
