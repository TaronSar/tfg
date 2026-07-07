"""CVAT <-> FiftyOne sync helpers for the human-in-the-loop curation loop.

All public functions accept an already-loaded FiftyOne dataset object so
that this module can be imported (and tested) without triggering a live
FiftyOne/MongoDB connection.  FiftyOne is only accessed inside function
bodies where the caller has already established the connection."""
from __future__ import annotations

from loguru import logger

from src.ood.common.config_loader import load_dataset_config
from src.ood.curation._typing import FiftyOneDatasetLike

# ---------------------------------------------------------------------------
# Configuration constants shared across curation workflow
# ---------------------------------------------------------------------------

RELABEL_TAG_PREFIX: str = "to_"
RELABEL_TAG: str = "relabel"
EXCLUDE_TAG: str = "exclude"
CVAT_EXCLUDE_LABEL: str = "Exclude"
_DATASET_CFG = load_dataset_config()
RELABEL_TAGS: tuple[str, ...] = tuple(
    f"{RELABEL_TAG_PREFIX}{class_name}" for class_name in _DATASET_CFG["classes"]
)


# ---------------------------------------------------------------------------
# Pure helpers (no I/O, fully unit-testable)
# ---------------------------------------------------------------------------


def _annotation_to_label(sample) -> str | None:
    """Extract the top-level label from a CVAT ``cvat_relabel`` field.

    Supports both ``Classification`` (``.label``) and ``Classifications``
    (``.classifications[0].label``) structures returned by FiftyOne after
    ``load_annotations()``.

    Args:
        sample: A FiftyOne sample that exposes ``get_field("cvat_relabel")``.

    Returns:
        The label string, or ``None`` if no annotation is present.
    """
    ann = sample.get_field("cvat_relabel")
    if ann is None:
        return None
    if hasattr(ann, "label"):
        return ann.label
    if hasattr(ann, "classifications") and ann.classifications:
        return ann.classifications[0].label
    return None


# ---------------------------------------------------------------------------
# CVAT push / pull orchestration
# ---------------------------------------------------------------------------


def push_relabel_queue(
    dataset: FiftyOneDatasetLike,
    anno_key: str,
    cvat_url: str,
    username: str,
    password: str,
    classes: list[str],
    skip_filter: bool = False,
) -> None:
    """Push all ``relabel``-tagged samples to a new CVAT annotation task.

    Args:
        dataset: A loaded FiftyOne dataset or pre-filtered view.
        anno_key: Unique annotation key to track this CVAT round.
        cvat_url: CVAT server URL (e.g. ``http://192.168.2.1:8080``).
        username: CVAT username.
        password: CVAT password.
        classes: Classification class list exposed to annotators.
        skip_filter: When ``True``, assume dataset is already filtered to relabel samples.
    """
    view = dataset if skip_filter else dataset.match_tags(RELABEL_TAG)
    n_samples = len(view)
    if n_samples == 0:
        logger.warning(f"No samples tagged '{RELABEL_TAG}' — nothing to push.")
        return

    logger.info(f"Pushing {n_samples} samples to CVAT (anno_key={anno_key!r}) …")
    view.annotate(
        anno_key,
        label_schema={"cvat_relabel": {"type": "classifications", "classes": classes}},
        url=cvat_url,
        username=username,
        password=password,
        launch_editor=True,
    )
    logger.success(
        f"Pushed {n_samples} samples. Complete annotations in CVAT, "
        "then run: curate.py pull"
    )


def apply_cvat_annotations(
    dataset: FiftyOneDatasetLike,
    anno_key: str,
    cvat_url: str,
    username: str,
    password: str,
) -> int:
    """Pull CVAT annotations and apply them as FiftyOne tags in-place.

    Tag mapping rules applied to every sample still carrying the
    ``relabel`` tag:

    * CVAT ``Exclude`` label → add ``exclude`` tag, strip ``relabel`` and
      all ``to_*`` tags.
    * Known class label (from configured CLASSES) → add the matching
      ``to_<Class>`` tag, strip the ``relabel`` tag.
    * No annotation → sample left unchanged.

    Args:
        dataset: A loaded FiftyOne dataset.
        anno_key: Annotation key that was used during the matching push.
        cvat_url: CVAT server URL.
        username: CVAT username.
        password: CVAT password.

    Returns:
        Number of samples whose tags were updated.
    """
    logger.info(f"Loading annotations for anno_key={anno_key!r} from CVAT …")
    dataset.load_annotations(
        anno_key,
        url=cvat_url,
        username=username,
        password=password,
    )

    dataset_cfg = load_dataset_config()
    classes = dataset_cfg["classes"]

    updates = 0
    for sample in dataset.match_tags(RELABEL_TAG):
        cvat_label = _annotation_to_label(sample)
        if cvat_label is None:
            continue

        if cvat_label == CVAT_EXCLUDE_LABEL:
            if EXCLUDE_TAG not in sample.tags:
                sample.tags.append(EXCLUDE_TAG)
            sample.tags = [t for t in sample.tags if t not in RELABEL_TAGS and t != RELABEL_TAG]
            updates += 1
            sample.save()
            continue

        if cvat_label in classes:
            to_tag = f"{RELABEL_TAG_PREFIX}{cvat_label}"
            if to_tag not in sample.tags:
                sample.tags.append(to_tag)
            sample.tags = [t for t in sample.tags if t != RELABEL_TAG]
            updates += 1
            sample.save()

    dataset.save()
    logger.info(f"Synced {updates} samples from CVAT annotations into FiftyOne tags")
    logger.success("Annotations loaded. Review in FiftyOne, then run: curate.py status")
    return updates
