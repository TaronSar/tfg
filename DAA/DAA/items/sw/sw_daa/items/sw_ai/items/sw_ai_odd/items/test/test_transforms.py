"""Tests for image transforms and corruption helpers."""
from __future__ import annotations

import numpy as np
import pytest

from src.ood.common.transforms import (
    CORRUPTIONS,
    IMG_SIZE,
    darken,
    make_corrupted_transform,
    make_eval_transform,
    make_train_transform,
)


class TestDarken:
    @pytest.mark.parametrize("severity", [1, 2, 3, 4, 5])
    def test_output_is_darker_or_equal(self, sample_rgb_array, severity):
        out = darken(sample_rgb_array, severity=severity)
        assert out.max() <= sample_rgb_array.max()

    def test_output_dtype_uint8(self, sample_rgb_array):
        out = darken(sample_rgb_array)
        assert out.dtype == np.uint8

    def test_higher_severity_is_darker(self, sample_rgb_array):
        out1 = darken(sample_rgb_array, severity=1)
        out5 = darken(sample_rgb_array, severity=5)
        assert out5.mean() < out1.mean()

    def test_no_negative_values(self, sample_rgb_array):
        for sev in range(1, 6):
            assert darken(sample_rgb_array, sev).min() >= 0


class TestTransformPipelines:
    @pytest.mark.parametrize(
        "make_fn", [make_train_transform, make_eval_transform, make_corrupted_transform],
    )
    def test_output_tensor_shape(self, sample_pil_image, make_fn):
        t = make_fn(IMG_SIZE)
        out = t(sample_pil_image)
        import torch

        assert out.shape == torch.Size([3, IMG_SIZE, IMG_SIZE])

    def test_train_and_eval_same_inference_shape(self, sample_pil_image):
        train_t = make_train_transform()
        eval_t = make_eval_transform()

        xt = train_t(sample_pil_image)
        xe = eval_t(sample_pil_image)
        assert xt.shape == xe.shape


class TestCorruptionsConstant:
    def test_contains_darken(self):
        assert "darken" in CORRUPTIONS

    def test_all_are_strings(self):
        assert all(isinstance(c, str) for c in CORRUPTIONS)
