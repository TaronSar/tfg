"""Curation status aggregation helpers for the FiftyOne review loop.

The sole public function :func:`get_curation_status` accepts an
already-loaded FiftyOne dataset so that this module can be imported (and
tested) without a live FiftyOne/MongoDB connection.
"""
from __future__ import annotations

from src.ood.curation._typing import FiftyOneDatasetLike
from src.ood.curation.cvat_sync import EXCLUDE_TAG, RELABEL_TAG, RELABEL_TAGS


def get_curation_status(dataset: FiftyOneDatasetLike) -> dict:
    """Aggregate curation tag counts from a FiftyOne dataset.

    Args:
        dataset: A loaded FiftyOne dataset.

    Returns:
        Dict with the following keys:

        * ``total`` (int) — total number of samples.
        * ``n_excluded`` (int) — samples tagged ``exclude``.
        * ``relabel_counts`` (dict[str, int]) — per ``to_*`` tag counts;
          only tags with count > 0 are included.
        * ``n_relabeled`` (int) — sum of all ``to_*`` tag counts.
        * ``n_relabel_queue`` (int) — samples tagged ``relabel``
          (pending CVAT push/pull).
        * ``pending_runs`` (list[str]) — annotation run keys whose
          config status is not ``"complete"``.
    """
    total = len(dataset)
    n_excluded = len(dataset.match_tags(EXCLUDE_TAG))

    relabel_counts: dict[str, int] = {}
    for tag in RELABEL_TAGS:
        n = len(dataset.match_tags(tag))
        if n > 0:
            relabel_counts[tag] = n
    n_relabeled = sum(relabel_counts.values())
    n_relabel_queue = len(dataset.match_tags(RELABEL_TAG))

    anno_runs = dataset.list_annotation_runs()
    pending_runs: list[str] = []
    for run_key in anno_runs:
        info = dataset.get_annotation_info(run_key)
        config = info.config
        if hasattr(config, "status") and config.status != "complete":
            pending_runs.append(run_key)

    return {
        "total": total,
        "n_excluded": n_excluded,
        "relabel_counts": relabel_counts,
        "n_relabeled": n_relabeled,
        "n_relabel_queue": n_relabel_queue,
        "pending_runs": pending_runs,
    }
