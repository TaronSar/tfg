"""Tests for the Cleanlab data-cleaning module."""
from __future__ import annotations

from unittest.mock import MagicMock

import numpy as np
import pandas as pd
import pytest

from src.ood.cleaning.auditor import build_cleaning_mask, generate_report

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture()
def mock_datalab_with_outliers():
    """Datalab mock where samples 1 and 3 are outliers."""
    lab = MagicMock()
    lab.get_info.return_value = {"num_examples": 5}

    outlier_df = pd.DataFrame({
        "is_outlier_issue": [False, True, False, True, False],
        "outlier_score": [0.9, 0.1, 0.8, 0.05, 0.7],
    })
    near_dup_df = pd.DataFrame({
        "is_near_duplicate_issue": [False, False, False, False, False],
        "near_duplicate_score": [0.9, 0.9, 0.9, 0.9, 0.9],
    })

    def get_issues(issue_type):
        if issue_type == "outlier":
            return outlier_df
        if issue_type == "near_duplicate":
            return near_dup_df
        raise ValueError(f"Unknown issue type: {issue_type}")

    lab.get_issues = get_issues
    return lab


@pytest.fixture()
def mock_datalab_with_duplicates():
    """Datalab mock where samples 0 and 2 are near-duplicates."""
    lab = MagicMock()
    lab.get_info.return_value = {"num_examples": 4}

    outlier_df = pd.DataFrame({
        "is_outlier_issue": [False, False, False, False],
        "outlier_score": [0.9, 0.8, 0.7, 0.6],
    })
    near_dup_df = pd.DataFrame({
        "is_near_duplicate_issue": [True, False, True, False],
        "near_duplicate_score": [0.1, 0.9, 0.1, 0.9],
    })

    def get_issues(issue_type):
        if issue_type == "outlier":
            return outlier_df
        if issue_type == "near_duplicate":
            return near_dup_df
        raise ValueError(f"Unknown issue type: {issue_type}")

    lab.get_issues = get_issues
    return lab


@pytest.fixture()
def mock_datalab_for_report():
    """Datalab mock with summary and issue details for report generation."""
    lab = MagicMock()
    lab.get_info.return_value = {"num_examples": 10}

    summary_df = pd.DataFrame([
        {"issue_type": "outlier", "num_issues": 2},
        {"issue_type": "near_duplicate", "num_issues": 1},
        {"issue_type": "label", "num_issues": 0},
    ])
    lab.get_issue_summary.return_value = summary_df

    outlier_df = pd.DataFrame({
        "is_outlier_issue": [False] * 8 + [True, True],
        "outlier_score": [0.9] * 8 + [0.05, 0.03],
    })
    near_dup_df = pd.DataFrame({
        "is_near_duplicate_issue": [False] * 9 + [True],
        "near_duplicate_score": [0.9] * 9 + [0.1],
    })
    label_df = pd.DataFrame({
        "is_label_issue": [False] * 10,
        "label_score": [0.95] * 10,
    })

    def get_issues(issue_type):
        return {"outlier": outlier_df, "near_duplicate": near_dup_df, "label": label_df}[
            issue_type
        ]

    lab.get_issues = get_issues
    return lab


# ── Tests: build_cleaning_mask ────────────────────────────────────────────────


class TestBuildCleaningMask:
    def test_outlier_removal(self, mock_datalab_with_outliers):
        mask = build_cleaning_mask(mock_datalab_with_outliers, ["outlier"])
        expected = np.array([True, False, True, False, True])
        np.testing.assert_array_equal(mask, expected)

    def test_near_duplicate_removal(self, mock_datalab_with_duplicates):
        mask = build_cleaning_mask(mock_datalab_with_duplicates, ["near_duplicate"])
        expected = np.array([False, True, False, True])
        np.testing.assert_array_equal(mask, expected)

    def test_combined_removal(self, mock_datalab_with_outliers):
        mask = build_cleaning_mask(
            mock_datalab_with_outliers, ["outlier", "near_duplicate"]
        )
        # outlier removes 1, 3; near_dup removes none → keep 0, 2, 4
        expected = np.array([True, False, True, False, True])
        np.testing.assert_array_equal(mask, expected)

    def test_empty_filter_list(self, mock_datalab_with_outliers):
        mask = build_cleaning_mask(mock_datalab_with_outliers, [])
        expected = np.ones(5, dtype=bool)
        np.testing.assert_array_equal(mask, expected)

    def test_unknown_issue_type_skipped(self, mock_datalab_with_outliers):
        mask = build_cleaning_mask(
            mock_datalab_with_outliers, ["nonexistent_issue_type"]
        )
        expected = np.ones(5, dtype=bool)
        np.testing.assert_array_equal(mask, expected)


# ── Tests: generate_report ────────────────────────────────────────────────────


class TestGenerateReport:
    def test_report_structure(self, mock_datalab_for_report):
        report = generate_report(mock_datalab_for_report, "train")
        assert report["split"] == "train"
        assert report["num_examples"] == 10
        assert isinstance(report["issue_summary"], list)
        assert len(report["issue_summary"]) == 3
        assert isinstance(report["per_issue_details"], dict)

    def test_issue_summary_contents(self, mock_datalab_for_report):
        report = generate_report(mock_datalab_for_report, "val")
        summary = {s["issue_type"]: s["num_issues"] for s in report["issue_summary"]}
        assert summary["outlier"] == 2
        assert summary["near_duplicate"] == 1
        assert summary["label"] == 0

    def test_flagged_indices_present(self, mock_datalab_for_report):
        report = generate_report(mock_datalab_for_report, "test")
        outlier_detail = report["per_issue_details"]["outlier"]
        assert "flagged_indices" in outlier_detail
        assert 8 in outlier_detail["flagged_indices"]
        assert 9 in outlier_detail["flagged_indices"]

    def test_score_statistics(self, mock_datalab_for_report):
        report = generate_report(mock_datalab_for_report, "train")
        outlier_detail = report["per_issue_details"]["outlier"]
        assert "scores_min" in outlier_detail
        assert "scores_max" in outlier_detail
        assert "scores_mean" in outlier_detail
        assert outlier_detail["scores_min"] < outlier_detail["scores_max"]
