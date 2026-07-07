"""Shared pytest fixtures for the OOD test suite."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image


@pytest.fixture()
def tmp_dir(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture()
def sample_rgb_array() -> np.ndarray:
    """100×200 uint8 RGB array (non-zero so corruptions have visible effect)."""
    rng = np.random.default_rng(42)
    return rng.integers(80, 200, size=(100, 200, 3), dtype=np.uint8)


@pytest.fixture()
def sample_pil_image(sample_rgb_array: np.ndarray) -> Image.Image:
    return Image.fromarray(sample_rgb_array)


@pytest.fixture()
def small_jsonl(tmp_path: Path) -> Path:
    """3-record JSONL file with Urban/Non-urban/Water labels."""
    records = [
        {"img_name": "a.png", "label": "Urban", "flight_id": "flt1", "path": "part1/Images/flt1/a.png", "time": "0001", "confidence": 0.95},
        {"img_name": "b.png", "label": "Non-urban", "flight_id": "flt2", "path": "part1/Images/flt2/b.png", "time": "0002", "confidence": 0.90},
        {"img_name": "c.png", "label": "Water", "flight_id": "flt3", "path": "part1/Images/flt3/c.png", "time": "0003", "confidence": 0.92},
    ]
    p = tmp_path / "test.jsonl"
    with open(p, "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    return p
