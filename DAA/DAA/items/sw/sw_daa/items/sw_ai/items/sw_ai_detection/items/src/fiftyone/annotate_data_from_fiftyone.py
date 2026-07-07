import argparse
import json
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from loguru import logger

import fiftyone as fo
from src.fiftyone._utils import (
    apply_label_filters,
    apply_sample_tag_filters,
    configure_fiftyone,
    parse_label_filters,
)

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)

CVAT_URL = os.environ.get("CVAT_URL", "http://localhost:8080")
CVAT_USERNAME = os.environ.get("FIFTYONE_CVAT_USERNAME")
CVAT_PASSWORD = os.environ.get("FIFTYONE_CVAT_PASSWORD")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for CVAT annotation upload.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Load a FiftyOne dataset into CVAT to annotate")
    parser.add_argument(
        "--dataset-name", required=True, help="Name of the FiftyOne dataset to annotate"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Filter samples by version field.",
    )
    parser.add_argument(
        "--include-labels",
        nargs="+",
        default=None,
        metavar="KEY=VALUE",
        help="Include only samples matching these KEY=VALUE label filters "
        "(e.g. --include-labels split=train)",
    )
    parser.add_argument(
        "--exclude-labels",
        nargs="+",
        default=None,
        metavar="KEY=VALUE",
        help="Exclude samples matching these KEY=VALUE label filters."
        " Applied after --include-labels.",
    )
    parser.add_argument(
        "--exclude-tags",
        nargs="+",
        required=False,
        help="Exclude samples that carry any of these sample-level tags (e.g. 'remove_flock').",
    )
    parser.add_argument(
        "--include-tags",
        nargs="+",
        required=False,
        help="Include only samples that carry any of these sample-level tags.",
    )
    parser.add_argument(
        "--anno-key",
        default=None,
        help="CVAT annotation run key (default: dataset name)",
    )
    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Whether to open the annotation editor in a browser",
    )
    parser.add_argument(
        "--video",
        action="store_true",
        help="Treat annotations as video tracks (use CVAT video/track editor)",
    )
    parser.add_argument(
        "--task-size",
        type=int,
        default=None,
        help="Upload samples to CVAT in tasks of this size (prevents very large single uploads)",
    )
    parser.add_argument(
        "--label-schema-json",
        type=str,
        required=True,
        help="Path to a JSON file containing the label schema dict for CVAT annotation",
    )
    args = parser.parse_args()

    return args


def annotate_dataset(
    dataset_name: str,
    version: str,
    label_schema: dict[str, Any],
    include_labels: dict[str, list[str]] | None = None,
    exclude_labels: dict[str, list[str]] | None = None,
    exclude_tags: list[str] | None = None,
    include_tags: list[str] | None = None,
    anno_key: str | None = None,
    open_browser=False,
    video: bool = False,
    task_size: int | None = None,
):
    """Upload a FiftyOne dataset view to CVAT for annotation.

    Args:
        dataset_name: Name of the FiftyOne dataset.
        version: Version label to filter samples by.
        label_schema: Schema dict passed to ``view.annotate()``.
        include_labels: Include only samples matching these ``{field: [values]}``.
        exclude_labels: Exclude samples matching these ``{field: [values]}``.
                        Applied after *include_labels*.
        exclude_tags: Sample tags whose presence should exclude a sample.
        include_tags: Sample tags whose presence should include a sample.
        anno_key: CVAT annotation run key. Defaults to *dataset_name*.
        open_browser: Launch CVAT editor in a browser.
        video: Use CVAT video/track annotation mode.
        task_size: Split upload into tasks of this size.
    """
    try:
        dataset = fo.load_dataset(name=dataset_name)
    except Exception as e:
        logger.error(f"Failed to load dataset {dataset_name}: {e}")
        return

    view = dataset.match_tags(f"v:{version}")
    if len(view) == 0:
        logger.error(f"No samples with version '{version}' in dataset '{dataset_name}'")
        return
    logger.info(f"Filtered to {len(view)} samples with version '{version}'")

    view = apply_label_filters(view, include_labels=include_labels, exclude_labels=exclude_labels)
    view = apply_sample_tag_filters(view, exclude_tags=exclude_tags, include_tags=include_tags)
    if len(view) == 0:
        logger.error(f"No samples remaining after filtering in dataset '{dataset_name}'")
        return
    logger.info(f"After filtering: {len(view)} samples")

    anno_key = anno_key if anno_key else dataset_name
    label_type = "tracks.detections" if video else "detections"

    view.annotate(
        anno_key,
        label_schema=label_schema,
        label_type=label_type,
        url=CVAT_URL,
        launch_editor=open_browser,
        username=CVAT_USERNAME,
        password=CVAT_PASSWORD,
        task_size=task_size,
    )


def main():
    configure_fiftyone()
    args = _parse_args()
    dataset_name = args.dataset_name
    logger.info("Annotating dataset...")
    with open(args.label_schema_json) as f:
        label_schema = json.load(f)

    annotate_dataset(
        dataset_name=dataset_name,
        version=args.version,
        label_schema=label_schema,
        include_labels=parse_label_filters(args.include_labels),
        exclude_labels=parse_label_filters(args.exclude_labels),
        exclude_tags=args.exclude_tags,
        include_tags=args.include_tags,
        anno_key=args.anno_key,
        open_browser=args.open_browser,
        video=args.video,
        task_size=args.task_size,
    )


if __name__ == "__main__":
    main()
