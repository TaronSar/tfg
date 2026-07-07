import argparse
import json
import os
import re
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, cast

import fiftyone.brain as fob
import fiftyone.zoo as foz
import torch
from dotenv import load_dotenv
from loguru import logger
from tqdm import tqdm

import fiftyone as fo
from fiftyone import ViewField as F
from src.fiftyone._utils import configure_fiftyone, launch_fiftyone_app

dotenv_path = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(str(dotenv_path), override=True)

LANCEDB_URI = os.environ.get("FIFTYONE_LANCEDB_URI", "/data/lancedb")

_STANDARD_ANN_KEYS = {
    "id",
    "image_id",
    "category_id",
    "bbox",
    "area",
    "iscrowd",
    "segmentation",
    "score",
    "track_id",
}


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments for FiftyOne data loading.

    Returns:
        Parsed arguments namespace.
    """
    parser = argparse.ArgumentParser(description="Load a COCO dataset into FiftyOne")
    parser.add_argument(
        "--load-mode",
        choices=["coco", "images", "video_frames"],
        required=True,
        help=(
            "Mode for loading data into FiftyOne. "
            "Use 'coco' to load from COCO annotations JSON, "
            "'images' to load all images from a directory, without annotations "
            "or 'video_frames' to load pre-extracted video frames without annotations"
        ),
    )
    parser.add_argument(
        "--dataset-name",
        required=True,
        help="FiftyOne dataset name",
    )
    parser.add_argument(
        "--images-dir",
        default=None,
        help="Path to images directory",
    )
    parser.add_argument(
        "--video-frames-dir",
        default=None,
        help=(
            "Scenario 3: path to a directory whose immediate subdirectories are per-video frame "
            "folders. Each subfolder name is treated as the video identifier. "
            "Mutually exclusive with --annotations-path and --images-extensions."
        ),
    )
    parser.add_argument(
        "--video-metadata-path",
        default=None,
        help=(
            "Optional JSON file mapping video subfolder names to metadata: "
            '{"video_001": {"fps": 30, "num_frames": 500, "file_name": "video_001.mp4"}}'
        ),
    )

    parser.add_argument(
        "--annotations-path",
        default=None,
        help="Path to COCO annotations JSON",
    )

    parser.add_argument(
        "--images-extensions",
        nargs="+",
        default=None,
        help="List of image file extensions to include",
    )
    parser.add_argument(
        "--version",
        required=True,
        help="FiftyOne dataset version (stored as a sample-level field)",
    )

    parser.add_argument(
        "--override",
        action="store_true",
        help="Override existing dataset if it exists",
    )

    parser.add_argument(
        "--append",
        action="store_true",
        help="Append samples to an existing dataset instead of recreating it",
    )

    parser.add_argument(
        "--label",
        nargs="+",
        default=None,
        metavar="KEY=VALUE",
        help=(
            "Add a fo.Classification label field to every sample. "
            "Format: KEY=VALUE. Repeatable. "
            "Example: --label split=train subset=balanced"
        ),
    )

    parser.add_argument(
        "--compute-embeddings",
        action="store_true",
        help="Compute embeddings for new samples (without running brain methods)",
    )
    parser.add_argument(
        "--compute-similarity",
        action="store_true",
        help="Compute dataset similarity using embeddings",
    )
    parser.add_argument(
        "--compute-duplicates",
        action="store_true",
        help="Compute near duplicates in the dataset using embeddings",
    )
    parser.add_argument(
        "--compute-uniqueness",
        action="store_true",
        help="Compute uniqueness scores for each sample in the dataset",
    )
    parser.add_argument(
        "--compute-visualization",
        action="store_true",
        help="Compute 2D visualization of the dataset using embeddings",
    )
    parser.add_argument(
        "--embeddings-model",
        default="dinov2-vitb14-reg-torch",
        help=(
            "Name of the model to use for computing embeddings (default: dinov2-vitb14-reg-torch)."
        ),
    )

    parser.add_argument(
        "--open-browser",
        action="store_true",
        help="Whether to open the annotation editor in a browser",
    )
    parser.add_argument(
        "--classes",
        nargs="+",
        default=None,
        help="Ordered class names to register as default classes",
    )
    args = parser.parse_args()

    return args


def _parse_labels(raw: list[str] | None) -> dict[str, str]:
    """Parse ``KEY=VALUE`` pairs from ``--label`` arguments."""
    if not raw:
        return {}
    labels: dict[str, str] = {}
    for item in raw:
        if "=" not in item:
            raise ValueError(
                f"Invalid --label format: '{item}'. Expected KEY=VALUE (e.g. split=train)"
            )
        key, value = item.split("=", 1)
        labels[key] = value
    return labels


def _apply_labels(sample: fo.Sample, labels: dict[str, str]) -> None:
    """Set ``fo.Classifications`` fields on a sample from a labels dict."""
    for key, value in labels.items():
        sample[key] = fo.Classifications(classifications=[fo.Classification(label=value)])


def _remove_version_from_dataset(
    dataset: fo.Dataset, version_view: Any, version: str
) -> tuple[int, int]:
    """Remove a version tag from samples; delete samples with no versions left.

    Args:
        dataset: FiftyOne dataset (used for orphan cleanup).
        version_view: Pre-filtered view of samples carrying ``version``.
        version: Version string (without ``v:`` prefix).

    Returns:
        Tuple of ``(n_updated, n_deleted)``.
    """
    n_updated = version_view.count()
    version_view.untag_samples(f"v:{version}")

    orphaned = dataset.match(F("tags").filter(F().starts_with("v:")).length() == 0)
    n_deleted = orphaned.count()
    if n_deleted > 0:
        dataset.delete_samples(orphaned)

    return n_updated, n_deleted


def _build_samples_from_coco_file(
    images_dir: str,
    coco: dict,
    version: str = "",
    labels: dict[str, str] | None = None,
) -> list[fo.Sample]:
    """Parse an extended COCO dict and return a list of FiftyOne samples.

    Handles the custom extensions beyond standard COCO:
    - ``images[*].video_id`` / ``frame_id`` → sample fields
    - ``videos[*]``            → sample fields ``video_path``, ``video_fps``, ``video_num_frames``
    - ``annotations[*].track_id``          → ``fo.Detection.index`` (FiftyOne tracking field)
    - ``annotations[*].airborne_metadata`` → ``fo.Detection.range_m`` / ``is_above_horizon``
    """
    categories = {c["id"]: c["name"] for c in coco.get("categories", [])}
    videos = {v["id"]: v for v in coco.get("videos", [])}
    images = {img["id"]: img for img in coco.get("images", [])}

    anns_by_image: dict[int, list] = defaultdict(list)
    for ann in coco.get("annotations", []):
        anns_by_image[ann["image_id"]].append(ann)

    samples = []
    for img in tqdm(images.values(), desc="Building FiftyOne samples ", unit="frame"):
        filepath = os.path.join(images_dir, img["file_name"])
        img_w = img.get("width") or 1
        img_h = img.get("height") or 1

        detections = []
        for ann in anns_by_image.get(img["id"], []):
            x, y, w, h = ann["bbox"]
            rel_box = [x / img_w, y / img_h, w / img_w, h / img_h]

            det_kwargs: dict = {
                "label": categories.get(ann["category_id"], "unknown"),
                "bounding_box": rel_box,
                "index": int(ann.get("track_id", -1)),
                "bbox_width": w,
                "bbox_height": h,
                "bbox_area": w * h,
            }
            if ann.get("score") is not None:
                det_kwargs["confidence"] = float(ann["score"])

            for key, value in ann.items():
                if key not in _STANDARD_ANN_KEYS:
                    det_kwargs[key] = value

            detections.append(fo.Detection(**det_kwargs))

        video = videos.get(img.get("video_id"), {})
        sample_kwargs: dict = {
            "filepath": filepath,
            "ground_truth": fo.Detections(detections=detections),
            "coco_image_id": int(img["id"]) if img.get("id") is not None else -1,
            "video_id": int(img.get("video_id")) if img.get("video_id") is not None else -1,
            "frame_id": int(img.get("frame_id")) if img.get("frame_id") is not None else -1,
            "video_path": video.get("file_name") if video.get("file_name") is not None else None,
            "video_fps": int(video.get("fps")) if video.get("fps") is not None else None,
            "video_num_frames": (
                int(video.get("num_frames")) if video.get("num_frames") is not None else None
            ),
            "num_detections": len(detections),
        }

        sample = fo.Sample(**sample_kwargs)
        sample.tags.append(f"v:{version}")
        _apply_labels(sample, labels or {})
        samples.append(sample)

    return samples


def _create_fiftyone(
    dataset_name: str,
    samples: list[fo.Sample],
    categories: list[str] | None = None,
) -> fo.Dataset:
    """Create or append samples to a FiftyOne dataset.

    Args:
        dataset_name: FiftyOne dataset name.
        samples: Samples to add.
        categories: Category names to register as default classes.

    Returns:
        The FiftyOne dataset.
    """
    if dataset_name in fo.list_datasets():
        dataset = fo.load_dataset(dataset_name)
        logger.info(f"Appending {len(samples)} samples to existing dataset '{dataset_name}'")
    else:
        dataset = fo.Dataset(name=dataset_name, persistent=True)

    if categories:
        existing = list(dataset.default_classes or [])
        merged = list(dict.fromkeys(existing + list(categories)))
        dataset.default_classes = merged

    try:
        dataset.add_sample_field("video_id", fo.IntField)
        dataset.add_sample_field("frame_id", fo.IntField)
        dataset.add_sample_field("num_detections", fo.IntField)
        dataset.add_sample_field("coco_image_id", fo.IntField)
        dataset.add_sample_field("video_path", fo.StringField)
        dataset.add_sample_field("video_fps", fo.IntField)
        dataset.add_sample_field("video_num_frames", fo.IntField)
    except Exception:
        pass

    dataset.add_samples(samples, progress=True)

    dataset.add_dynamic_sample_fields()
    dataset.compute_metadata()
    dataset.save()
    return cast(fo.Dataset, dataset)


def load_coco_dataset_into_fiftyone(
    annotations_path: str,
    images_dir: str,
    dataset_name: str,
    version: str,
    labels: dict[str, str] | None = None,
    classes: list[str] | None = None,
) -> fo.Dataset:
    """Load a COCO annotation file into FiftyOne.

    Args:
        annotations_path: Path to the COCO annotations JSON.
        images_dir: Root directory of image files.
        dataset_name: FiftyOne dataset name.
        version: Version label stored on each sample.
        labels: Extra classification labels to attach.
        classes: Extra class names to register alongside those in the COCO file.

    Returns:
        The FiftyOne dataset.
    """
    logger.info("Loading extended COCO JSON...")
    with open(annotations_path) as f:
        coco = json.load(f)
    samples = _build_samples_from_coco_file(images_dir, coco, version=version, labels=labels)

    coco_categories = [c["name"] for c in coco.get("categories", [])]
    extra_classes = classes or []
    all_categories = list(dict.fromkeys(coco_categories + extra_classes))
    logger.info(f"Found {len(coco_categories)} categories in COCO file: {coco_categories}")
    logger.info(f"Registered {len(all_categories)} categories: {all_categories}")
    logger.info("Adding samples to FiftyOne dataset...")
    dataset = _create_fiftyone(dataset_name, samples, categories=all_categories)
    logger.info(f"Dataset '{dataset_name}' loaded successfully with {dataset.count()} samples")

    return dataset


def load_images_into_fiftyone(
    images_dir: str,
    dataset_name: str,
    images_extensions: list[str],
    version: str,
    labels: dict[str, str] | None = None,
) -> fo.Dataset:
    """Load images from a directory into FiftyOne without annotations.

    Args:
        images_dir: Root directory to scan for images.
        dataset_name: FiftyOne dataset name.
        images_extensions: File extensions to include.
        version: Version label stored on each sample.
        labels: Extra classification labels to attach.

    Returns:
        The FiftyOne dataset.
    """
    images_root = Path(images_dir)
    extensions = {ext.lower() for ext in images_extensions}
    samples = [
        fo.Sample(filepath=str(img_path))
        for img_path in tqdm(images_root.rglob("*"), desc="Building FiftyOne samples", unit="image")
        if img_path.suffix.lower() in extensions
    ]
    for sample in samples:
        sample.tags.append(f"v:{version}")
        _apply_labels(sample, labels or {})

    dataset = _create_fiftyone(dataset_name, samples)
    logger.info(f"Dataset '{dataset_name}' loaded successfully with {dataset.count()} images")

    return dataset


def load_video_frames_into_fiftyone(
    video_frames_dir: str,
    dataset_name: str,
    images_extensions: list[str],
    video_metadata_path: str | None = None,
    version: str = "",
    labels: dict[str, str] | None = None,
) -> fo.Dataset:
    """Scenario 3: load pre-extracted video frames with video metadata.

    Directory layout expected::

        video_frames_dir/
            video_001/          <- one subdirectory per video
                frame_00001.jpg
                frame_00002.jpg
            video_002/
                ...

    Each subdirectory name is used as the video identifier.  Frame IDs are
    inferred from the trailing integer in each filename stem (e.g.
    ``frame_00042.jpg`` → ``frame_id=42``); falling back to alphabetical order.

    Args:
        video_frames_dir: Root directory containing per-video subdirectories.
        dataset_name: FiftyOne dataset name.
        video_metadata_path: Optional JSON mapping subdir names to metadata
            ``{fps, num_frames, file_name}``.
        images_extensions: File extensions to include (default: jpg/jpeg/png).
    """
    extensions = {ext.lower() for ext in images_extensions}

    frames_root = Path(video_frames_dir)

    video_metadata: dict[str, dict] = {}
    if video_metadata_path:
        with open(video_metadata_path) as f:
            video_metadata = json.load(f)

    samples = []
    video_id = 1

    for video_dir in sorted(frames_root.iterdir()):
        if not video_dir.is_dir():
            continue

        video_name = video_dir.name
        meta = video_metadata.get(video_name, {})
        fps = meta.get("fps")
        video_path = meta.get("file_name", video_name)

        frame_files = sorted(f for f in video_dir.rglob("*") if f.suffix.lower() in extensions)
        if not frame_files:
            logger.warning(f"No frames found in {video_dir}, skipping")
            continue

        num_frames = meta.get("num_frames", len(frame_files))

        for frame_order, frame_file in enumerate(frame_files):
            # Extract trailing integer from stem for frame_id; fall back to order
            nums = re.findall(r"\d+", frame_file.stem)
            frame_id = int(nums[-1]) if nums else frame_order

            sample = fo.Sample(
                filepath=str(frame_file),
                video_id=video_id,
                frame_id=frame_id,
                video_path=video_path,
                video_fps=fps,
                video_num_frames=num_frames,
            )
            sample.tags.append(f"v:{version}")
            _apply_labels(sample, labels or {})
            samples.append(sample)

        video_id += 1

    dataset = _create_fiftyone(dataset_name, samples)
    logger.info(
        f"Dataset '{dataset_name}' loaded with {dataset.count()} frames "
        f"from {video_id - 1} videos under {video_frames_dir}"
    )
    return dataset


def _handle_existing_version(
    dataset_name: str,
    version: str,
    override: bool,
    append: bool,
) -> None:
    """Handle version conflicts when the dataset already exists.

    - ``override``: strip the version tag from matching samples, delete
      orphans with no versions remaining, and clear brain runs.
    - ``append``: silently allow adding more samples with the same version.
    - Neither: raise ``ValueError``.

    Args:
        dataset_name: FiftyOne dataset name.
        version: Version label to check.
        override: Whether to remove the existing version.
        append: Whether appending is allowed.
    """
    try:
        dataset_exists = dataset_name in fo.list_datasets()
    except Exception as e:
        raise Exception(
            "Could not connect to FiftyOne database."
            " Ensure the FiftyOne DB is running and accessible."
        ) from e

    if not dataset_exists:
        return

    existing_dataset = fo.load_dataset(dataset_name)
    version_view = existing_dataset.match_tags(f"v:{version}")
    version_count = version_view.count()

    if version_count == 0:
        return

    if override:
        logger.warning(
            f"Removing version '{version}' from {version_count} samples "
            f"in dataset '{dataset_name}' in 5 seconds..."
        )
        time.sleep(5)
        logger.warning("Removing version tags...")
        for key in list(existing_dataset.list_brain_runs()):
            logger.info(f"Deleting stale brain run '{key}'...")
            existing_dataset.delete_brain_run(key)
        n_updated, n_deleted = _remove_version_from_dataset(existing_dataset, version_view, version)
        logger.info(
            f"Removed version from {n_updated} samples, "
            f"deleted {n_deleted} orphaned samples (no versions left)"
        )
        return

    if append:
        return

    raise ValueError(
        f"Version '{version}' already has {version_count} samples in "
        f"dataset '{dataset_name}'. Use --override to replace or --append to add more."
    )


def _validate_load_mode_args(
    load_mode: str,
    annotations_path: str | None,
    images_dir: str | None,
    images_extensions: list[str] | None,
    video_frames_dir: str | None,
) -> None:
    """Validate required arguments for each load mode.

    Args:
        load_mode: One of ``"coco"``, ``"images"``, ``"video_frames"``.
        annotations_path: COCO JSON path (required for ``"coco"`` mode).
        images_dir: Root directory for images (required for ``"coco"`` and ``"images"`` modes).
        images_extensions: File extensions to include (required for ``"images"`` and
                            ``"video_frames"`` modes).
        video_frames_dir: Directory of per-video frame folders
                            (required for ``"video_frames"`` mode).
    """
    if load_mode == "coco":
        assert annotations_path is not None, "annotations_path is required for coco load mode"
        assert images_dir is not None, "images_dir is required for coco load mode"
    elif load_mode == "images":
        assert images_dir is not None, "images_dir is required for images load mode"
        assert images_extensions is not None, "images_extensions is required for images load mode"
    elif load_mode == "video_frames":
        assert video_frames_dir is not None, (
            "video_frames_dir is required for video_frames load mode"
        )
        assert images_extensions is not None, (
            "images_extensions is required for video_frames load mode"
        )


def load_dataset(
    load_mode: str,
    images_dir: str | None,
    dataset_name: str,
    version: str,
    annotations_path: str | None = None,
    images_extensions: list[str] | None = None,
    video_frames_dir: str | None = None,
    video_metadata_path: str | None = None,
    override: bool = False,
    append: bool = False,
    labels: dict[str, str] | None = None,
    classes: list[str] | None = None,
    compute_embeddings: bool = False,
    compute_similarity: bool = False,
    compute_duplicates: bool = False,
    compute_uniqueness: bool = False,
    compute_visualization: bool = False,
    embeddings_model: str = "dinov2-vitb14-reg-torch",
    open_browser: bool = False,
) -> fo.Dataset:
    """High-level loader dispatching to coco/images/video_frames modes.

    Args:
        load_mode: One of ``"coco"``, ``"images"``, ``"video_frames"``.
        images_dir: Root directory for images.
        dataset_name: FiftyOne dataset name.
        version: Version label for loaded samples.
        annotations_path: COCO JSON path (required for ``"coco"`` mode).
        images_extensions: File extensions to include.
        video_frames_dir: Directory of per-video frame folders.
        video_metadata_path: JSON with video metadata.
        override: Delete existing samples with the same version.
        append: Append to existing samples instead of raising.
        labels: Extra classification labels.
        compute_embeddings: Compute embeddings for new samples.
        compute_similarity: Compute dataset similarity.
        compute_duplicates: Find near-duplicate samples.
        compute_uniqueness: Compute uniqueness scores.
        compute_visualization: Compute 2D visualization.
        embeddings_model: Zoo model name for embeddings.
        open_browser: Launch the FiftyOne app.

    Returns:
        The FiftyOne dataset.
    """
    if append and override:
        raise ValueError("--append and --override are mutually exclusive")

    _validate_load_mode_args(
        load_mode, annotations_path, images_dir, images_extensions, video_frames_dir
    )

    logger.info(f"Images extensions {images_extensions}")

    _handle_existing_version(dataset_name, version, override, append)

    if load_mode == "coco":
        assert annotations_path is not None
        assert images_dir is not None
        dataset = load_coco_dataset_into_fiftyone(
            annotations_path,
            images_dir,
            dataset_name,
            version=version,
            labels=labels,
            classes=classes,
        )
    elif load_mode == "video_frames":
        assert video_frames_dir is not None
        assert images_extensions is not None

        dataset = load_video_frames_into_fiftyone(
            video_frames_dir,
            dataset_name,
            images_extensions,
            video_metadata_path,
            version=version,
            labels=labels,
        )
    elif load_mode == "images":
        assert images_dir is not None
        assert images_extensions is not None
        dataset = load_images_into_fiftyone(
            images_dir, dataset_name, images_extensions, version=version, labels=labels
        )
    else:
        raise ValueError(f"Unsupported load mode: {load_mode}")

    needs_embeddings = (
        compute_embeddings
        or compute_similarity
        or compute_duplicates
        or compute_uniqueness
        or compute_visualization
    )
    if needs_embeddings:
        assert dataset is not None
        new_samples = dataset.exists("embeddings", bool=False)
        new_count = new_samples.count()
        if new_count > 0:
            logger.info(
                f"Computing embeddings for {new_count} new samples ({dataset.count()} total)..."
            )
            device = "cuda" if torch.cuda.is_available() else "cpu"
            logger.info(f"Using device: {device} for embedding computation")
            model = foz.load_zoo_model(embeddings_model, device=device)
            new_samples.compute_embeddings(model, embeddings_field="embeddings", progress=True)
        else:
            logger.info("All samples already have embeddings, skipping computation")

    if compute_similarity:
        logger.info("Computing dataset similarity...")
        assert dataset is not None
        for key in ("img_similarity", "gt_similarity"):
            if key in dataset.list_brain_runs():
                logger.info(f"Deleting existing brain run '{key}'...")
                dataset.delete_brain_run(key)
        fob.compute_similarity(
            dataset,
            embeddings="embeddings",
            brain_key="img_similarity",
            backend="lancedb",
            db_path=LANCEDB_URI,
            progress=True,
        )
        fob.compute_similarity(
            dataset,
            patches_field="ground_truth",
            embeddings="embeddings",
            brain_key="gt_similarity",
            backend="lancedb",
            db_path=LANCEDB_URI,
            progress=True,
        )

    if compute_duplicates:
        logger.info("Computing dataset near duplicates...")
        assert dataset is not None
        if "near_duplicates" in dataset.list_brain_runs():
            logger.info("Deleting existing brain run 'near_duplicates'...")
            dataset.delete_brain_run("near_duplicates")
        fob.compute_near_duplicates(
            dataset,
            embeddings="embeddings",
            threshold=0.95,
            progress=True,
        )

    if compute_uniqueness:
        logger.info("Computing dataset uniqueness...")
        assert dataset is not None
        if "uniqueness" in dataset.list_brain_runs():
            logger.info("Deleting existing brain run 'uniqueness'...")
            dataset.delete_brain_run("uniqueness")
        fob.compute_uniqueness(dataset, embeddings="embeddings", progress=True)

    if compute_visualization:
        logger.info("Computing dataset visualization...")
        assert dataset is not None
        if "viz" in dataset.list_brain_runs():
            logger.info("Deleting existing brain run 'viz'...")
            dataset.delete_brain_run("viz")
        fob.compute_visualization(dataset, embeddings="embeddings", brain_key="viz", progress=True)

    logger.info("Dataset analysis complete")

    if open_browser:
        launch_fiftyone_app(dataset, view=dataset.view())

    return dataset


def main():
    configure_fiftyone()
    args = _parse_args()

    load_dataset(
        load_mode=args.load_mode,
        images_dir=args.images_dir,
        dataset_name=args.dataset_name,
        annotations_path=args.annotations_path,
        images_extensions=args.images_extensions,
        video_frames_dir=args.video_frames_dir,
        video_metadata_path=args.video_metadata_path,
        version=args.version,
        override=args.override,
        append=args.append,
        labels=_parse_labels(args.label),
        classes=args.classes,
        compute_embeddings=args.compute_embeddings,
        compute_similarity=args.compute_similarity,
        compute_duplicates=args.compute_duplicates,
        compute_uniqueness=args.compute_uniqueness,
        compute_visualization=args.compute_visualization,
        embeddings_model=args.embeddings_model,
        open_browser=args.open_browser,
    )


if __name__ == "__main__":
    main()
