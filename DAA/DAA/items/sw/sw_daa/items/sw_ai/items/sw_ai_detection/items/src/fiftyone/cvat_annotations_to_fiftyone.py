import argparse
import os
from pathlib import Path
from typing import cast

from dotenv import load_dotenv
from loguru import logger

import fiftyone as fo
from src.fiftyone._utils import (
    configure_fiftyone,
    launch_fiftyone_app,
)

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)

CVAT_URL = os.environ.get("CVAT_URL", "http://localhost:8080")
CVAT_USERNAME = os.environ.get("FIFTYONE_CVAT_USERNAME")
CVAT_PASSWORD = os.environ.get("FIFTYONE_CVAT_PASSWORD")


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for CVAT annotation loading.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(
        description="Load a CVAT annotations back into FiftyOne dataset"
    )
    parser.add_argument(
        "--dataset-name", required=True, help="Name of the FiftyOne dataset to annotate"
    )
    parser.add_argument(
        "--version",
        required=True,
        help="Filter samples by version field.",
    )
    parser.add_argument(
        "--anno-key",
        default=None,
        help="CVAT annotation run key (must match the key used during annotation upload; default:"
        " dataset name)",
    )

    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Whether to open the annotation editor in a browser",
    )
    return parser.parse_args()


def _coerce_cvat_string_attrs(view: fo.Dataset) -> None:
    """Coerce CVAT string attributes back to numeric Python types in place.

    CVAT returns all custom attributes as strings.  This attempts to convert
    each string value to ``int`` first, then ``float``, falling back to the
    original string.  Works generically for any custom detection attribute
    (e.g. ``range_m``, ``is_above_horizon``, ``size_category``).
    """
    # FiftyOne built-in Detection fields — skip these during coercion.
    builtin = {"id", "label", "bounding_box", "confidence", "index", "tags", "attributes"}

    for sample in view.iter_samples(autosave=True):
        if not sample.ground_truth:
            continue
        for det in sample.ground_truth.detections:
            for attr_name in det.field_names:
                if attr_name in builtin:
                    continue
                val = det[attr_name]
                if not isinstance(val, str):
                    continue
                try:
                    det[attr_name] = int(val)
                except (ValueError, TypeError):
                    try:
                        det[attr_name] = float(val)
                    except (ValueError, TypeError):
                        pass


def export_dataset(
    dataset_name: str,
    version: str,
    anno_key: str | None = None,
    open_browser: bool = False,
) -> None:
    """Load CVAT annotations back into a FiftyOne dataset.

    Args:
        dataset_name: Name of the FiftyOne dataset.
        version: Version label used to display the relevant view when opening the browser.
        anno_key: CVAT annotation run key. Defaults to *dataset_name*.
        open_browser: Launch the FiftyOne app after loading.
    """
    try:
        dataset = cast(fo.Dataset, fo.load_dataset(name=dataset_name))
    except Exception as e:
        logger.error(f"Failed to load dataset {dataset_name}: {e}")
        return

    view = dataset.match_tags(f"v:{version}")
    if view.count() == 0:
        logger.error(f"No samples with version '{version}' in dataset '{dataset_name}'")
        return
    logger.info(f"Filtered to {view.count()} samples with version '{version}'")

    anno_key = anno_key if anno_key else dataset_name

    dataset.load_annotations(
        anno_key,
        progress=True,
        url=CVAT_URL,
        username=CVAT_USERNAME,
        password=CVAT_PASSWORD,
    )

    _coerce_cvat_string_attrs(view)

    if open_browser:
        launch_fiftyone_app(dataset, view=view.view())


def main():
    configure_fiftyone()
    args = _parse_args()
    dataset_name = args.dataset_name
    logger.info("Exporting dataset...")
    export_dataset(
        dataset_name=dataset_name,
        version=args.version,
        anno_key=args.anno_key,
        open_browser=args.open_browser,
    )


if __name__ == "__main__":
    main()
