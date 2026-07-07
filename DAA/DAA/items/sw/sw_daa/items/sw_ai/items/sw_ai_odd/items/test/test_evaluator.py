"""Tests for OOD detection evaluator utilities."""
from __future__ import annotations

import numpy as np
import pytest

from src.ood.train.evaluator import auroc_fpr95


class TestAurocFpr95:
    def test_perfect_separation(self):
        """When ID scores are all higher than OOD, AUROC=1, FPR95≈0."""
        s_id = np.linspace(5, 10, 100)
        s_ood = np.linspace(0, 4, 100)
        auroc, fpr95 = auroc_fpr95(s_id, s_ood)
        assert auroc == pytest.approx(1.0)
        assert fpr95 == pytest.approx(0.0)

    def test_random_scores_auroc_near_half(self):
        """Random scores should give AUROC close to 0.5."""
        rng = np.random.default_rng(0)
        s_id = rng.standard_normal(200)
        s_ood = rng.standard_normal(200)
        auroc, _ = auroc_fpr95(s_id, s_ood)
        assert 0.3 < auroc < 0.7

    def test_auroc_in_unit_interval(self):
        rng = np.random.default_rng(1)
        s_id = rng.standard_normal(50)
        s_ood = rng.standard_normal(50)
        auroc, fpr95 = auroc_fpr95(s_id, s_ood)
        assert 0.0 <= auroc <= 1.0
        assert 0.0 <= fpr95 <= 1.0

    def test_returns_floats(self):
        s_id = np.array([2.0, 3.0, 4.0])
        s_ood = np.array([0.0, 1.0, 1.5])
        auroc, fpr95 = auroc_fpr95(s_id, s_ood)
        assert isinstance(auroc, float)
        assert isinstance(fpr95, float)

    def test_inverted_separation_auroc_near_zero(self):
        """When OOD scores are higher than ID, AUROC ≈ 0 (wrong direction)."""
        s_id = np.linspace(0, 1, 100)
        s_ood = np.linspace(2, 3, 100)
        auroc, _ = auroc_fpr95(s_id, s_ood)
        assert auroc < 0.1
