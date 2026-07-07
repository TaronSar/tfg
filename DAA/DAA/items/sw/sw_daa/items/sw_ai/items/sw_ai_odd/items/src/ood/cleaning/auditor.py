"""Data quality auditing and cleaning utilities.

Provides Cleanlab Datalab integration for automated detection of:
  - Label errors and annotation issues
  - Outliers and anomalies
  - Near-duplicates (data leakage)
  - Class imbalance problems
  - Non-IID data distribution issues
"""
from __future__ import annotations

from typing import Any

import numpy as np
from loguru import logger


def run_datalab_audit(
    labels: list[str],
    features: np.ndarray,
    pred_probs: np.ndarray,
) -> Any:
    """Run a full Cleanlab Datalab audit on a dataset split.

    Initialises a ``Datalab`` instance with the given labels, then calls
    ``find_issues`` with both feature embeddings and prediction
    probabilities so that all supported issue types are detected.

    Args:
        labels: Per-sample string labels (e.g. ``["Urban", "Water", ...]``).
        features: Embedding matrix of shape ``(N, D)``.
        pred_probs: Out-of-sample prediction probabilities of shape
            ``(N, num_classes)``.

    Returns:
        A ``cleanlab.Datalab`` instance with issues already computed.
    """
    from cleanlab import Datalab

    data_dict = {"label": labels}
    lab = Datalab(data=data_dict, label_name="label")
    lab.find_issues(features=features, pred_probs=pred_probs)
    return lab


def build_cleaning_mask(
    datalab: Any,
    auto_filter_issues: list[str],
) -> np.ndarray:
    """Build a boolean *keep* mask that drops samples flagged by Datalab.

    For each issue type in *auto_filter_issues* the corresponding
    ``is_<type>_issue`` column is queried.  Any sample flagged by at
    least one issue type is marked for removal.

    Args:
        datalab: A ``Datalab`` instance returned by
            :func:`run_datalab_audit`.
        auto_filter_issues: Issue type names to auto-filter
            (e.g. ``["outlier", "near_duplicate"]``).

    Returns:
        Boolean NumPy array of length ``N`` where ``True`` means
        *keep* the sample and ``False`` means *remove* it.
    """
    n = datalab.get_info("statistics")["num_examples"]
    remove = np.zeros(n, dtype=bool)

    for issue_type in auto_filter_issues:
        flagged = _get_flagged_mask(datalab, issue_type)
        if flagged is not None:
            remove |= flagged

    keep = ~remove
    logger.info(
        f"Cleaning mask: keeping {int(keep.sum())}/{n} samples "
        f"(removing {int(remove.sum())})"
    )
    return keep


def _get_flagged_mask(datalab: Any, issue_type: str) -> np.ndarray | None:
    """Extract the boolean flagged-sample mask for a single issue type.

    Args:
        datalab: A ``Datalab`` instance returned by
            :func:`run_datalab_audit`.
        issue_type: Datalab issue type name (e.g. ``"outlier"``).

    Returns:
        Boolean NumPy array of length ``N`` where ``True`` marks a
        flagged sample, or ``None`` if the issue type is unavailable.
    """
    try:
        issues_df = datalab.get_issues(issue_type)
    except ValueError:
        logger.warning(f"Issue type '{issue_type}' not found — skipping.")
        return None

    col = f"is_{issue_type}_issue"
    if col not in issues_df.columns:
        logger.warning(f"Column '{col}' missing in {issue_type} issues — skipping.")
        return None

    flagged = issues_df[col].to_numpy().astype(bool)
    logger.info(f"  {issue_type}: {int(flagged.sum())} issues flagged for removal")
    return flagged


def generate_report(datalab: Any, split_name: str) -> dict:
    """Build a JSON-serialisable audit report from a Datalab instance.

    Delegates to :func:`_build_issue_summary` for the high-level table
    and :func:`_extract_issue_details` for per-type score statistics and
    flagged indices.

    Args:
        datalab: A ``Datalab`` instance returned by
            :func:`run_datalab_audit`.
        split_name: Human-readable split identifier (e.g. ``"train"``).

    Returns:
        Dict with keys ``split``, ``num_examples``, ``issue_summary``
        (list of per-type dicts), and ``per_issue_details`` mapping each
        issue type to its score statistics and flagged indices.
    """
    summary_df = datalab.get_issue_summary()
    issue_summary = _build_issue_summary(summary_df)
    per_issue_details = _extract_issue_details(datalab, summary_df)

    stats = datalab.get_info("statistics")
    return {
        "split": split_name,
        "num_examples": int(stats["num_examples"]),
        "issue_summary": issue_summary,
        "per_issue_details": per_issue_details,
    }


def _build_issue_summary(summary_df) -> list[dict]:
    """Convert the Datalab issue-summary DataFrame to a list of dicts.

    Args:
        summary_df: DataFrame returned by ``datalab.get_issue_summary()``.

    Returns:
        List of ``{"issue_type": str, "num_issues": int}`` dicts.
    """
    return [
        {"issue_type": row["issue_type"], "num_issues": int(row["num_issues"])}
        for _, row in summary_df.iterrows()
    ]


def _extract_issue_details(datalab: Any, summary_df) -> dict[str, dict]:
    """Extract per-issue-type score statistics and flagged indices.

    Args:
        datalab: A ``Datalab`` instance returned by
            :func:`run_datalab_audit`.
        summary_df: DataFrame returned by ``datalab.get_issue_summary()``.

    Returns:
        Dict mapping each issue type name to a detail dict with optional
        keys ``scores_min``, ``scores_max``, ``scores_mean``, and
        ``flagged_indices``.
    """
    per_issue_details: dict[str, dict] = {}

    for _, row in summary_df.iterrows():
        issue_type = row["issue_type"]
        try:
            issues_df = datalab.get_issues(issue_type)
        except (ValueError, KeyError):
            continue

        detail: dict[str, Any] = {}

        score_col = f"{issue_type}_score"
        if score_col in issues_df.columns:
            scores = issues_df[score_col].to_numpy()
            detail["scores_min"] = float(np.nanmin(scores))
            detail["scores_max"] = float(np.nanmax(scores))
            detail["scores_mean"] = float(np.nanmean(scores))

        flag_col = f"is_{issue_type}_issue"
        if flag_col in issues_df.columns:
            detail["flagged_indices"] = issues_df.index[issues_df[flag_col]].tolist()

        per_issue_details[issue_type] = detail

    return per_issue_details
