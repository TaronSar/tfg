"""Tests for image corruption utilities (no GPU, no NAS required)."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from src.ood.preprocessing.corruptions import (
    apply_corruption,
    corrupted_full_path,
    preprocess_for_corruption,
    process_single_image,
)


class TestApplyCorruption:
    @pytest.mark.parametrize("severity", [1, 3, 5])
    def test_darken_returns_uint8(self, sample_rgb_array, severity):
        out = apply_corruption(sample_rgb_array, "darken", severity)
        assert out.dtype == np.uint8

    @pytest.mark.parametrize("severity", [1, 3, 5])
    def test_darken_output_shape_preserved(self, sample_rgb_array, severity):
        out = apply_corruption(sample_rgb_array, "darken", severity)
        assert out.shape == sample_rgb_array.shape

    @pytest.mark.parametrize("severity", [1, 5])
    def test_darken_makes_darker(self, sample_rgb_array, severity):
        out = apply_corruption(sample_rgb_array, "darken", severity)
        assert int(out.mean()) < int(sample_rgb_array.mean())

    def test_darken_no_negative(self, sample_rgb_array):
        out = apply_corruption(sample_rgb_array, "darken", 1)
        assert out.min() >= 0


class TestPreprocessForCorruption:
    def test_returns_uint8_rgb(self, tmp_dir: Path, sample_rgb_array: np.ndarray):
        p = tmp_dir / "img.png"
        Image.fromarray(sample_rgb_array).save(p)
        arr = preprocess_for_corruption(p)
        assert arr.dtype == np.uint8
        assert arr.ndim == 3
        assert arr.shape[2] == 3

    def test_shape_matches_source(self, tmp_dir: Path, sample_rgb_array: np.ndarray):
        p = tmp_dir / "img.png"
        Image.fromarray(sample_rgb_array).save(p)
        arr = preprocess_for_corruption(p)
        assert arr.shape == sample_rgb_array.shape


class TestProcessSingleImage:
    def _make_rec(self, flight_id: str = "flt0", img_name: str = "a.png") -> dict:
        return {
            "img_name": img_name,
            "label": "Urban",
            "flight_id": flight_id,
            "path": f"part1/Images/{flight_id}/{img_name}",
            "time": "0001",
        }

    def test_returns_one_record_per_severity(self, tmp_dir: Path, sample_rgb_array: np.ndarray):
        fid = "flt0"
        img_name = "frame.png"
        # Create a fake AOT directory structure
        img_dir = tmp_dir / "part1" / "Images" / fid
        img_dir.mkdir(parents=True)
        Image.fromarray(sample_rgb_array).save(img_dir / img_name)

        rec = self._make_rec(fid, img_name)
        results = process_single_image(
            rec=rec,
            corruption_name="darken",
            corrupted_full_img_dir=tmp_dir / "corrupted",
            aot_root=tmp_dir,
            severities=[1, 3, 5],
        )
        assert len(results) == 3
        for r in results:
            assert r["type"] == "darken"
            assert r["label"] == "Urban"
        assert {r["severity"] for r in results} == {1, 3, 5}

    def test_missing_image_returns_empty(self, tmp_dir: Path):
        rec = self._make_rec("nonexistent_flt", "missing.png")
        results = process_single_image(
            rec=rec,
            corruption_name="darken",
            corrupted_full_img_dir=tmp_dir / "corrupted",
            aot_root=tmp_dir,
            severities=[1, 2],
        )
        assert results == []

    def test_output_png_exists(self, tmp_dir: Path, sample_rgb_array: np.ndarray):
        fid = "flt1"
        img_name = "img.png"
        img_dir = tmp_dir / "part1" / "Images" / fid
        img_dir.mkdir(parents=True)
        Image.fromarray(sample_rgb_array).save(img_dir / img_name)

        rec = self._make_rec(fid, img_name)
        corrupted_dir = tmp_dir / "corrupted"
        process_single_image(
            rec=rec,
            corruption_name="darken",
            corrupted_full_img_dir=corrupted_dir,
            aot_root=tmp_dir,
            severities=[2],
        )
        expected = corrupted_full_path(rec["path"], "darken", 2, corrupted_dir)
        assert expected.exists()
