"""Tests for flight-disjoint dataset splitting and class balancing."""
from __future__ import annotations

import json
import tempfile
from collections import Counter
from pathlib import Path

from src.ood.dataset.clip_classifier import (
    crop_to_frame_path,
    load_detection_frame_manifest,
    split_by_flight,
    undersample_to_min,
)
from src.ood.common.path_utils import parse_frame_path


def _make_records(per_class: dict[str, list[str]]) -> list[dict]:
    """Build fake records: {label → list of flight_ids}."""
    recs = []
    for label, flight_ids in per_class.items():
        for i, fid in enumerate(flight_ids):
            recs.append({
                "img_name": f"{fid}_{i}.png",
                "label": label,
                "flight_id": fid,
                "path": f"part1/Images/{fid}/{fid}_{i}.png",
                "time": str(i).zfill(4),
                "confidence": 0.95,
            })
    return recs


class TestUndersampleToMin:
    def test_all_classes_equal_count(self):
        recs = _make_records({
            "Urban": ["f1", "f1", "f1", "f2", "f2"],
            "Non-urban": ["f3"],
            "Water": ["f4", "f4", "f4"],
        })
        balanced = undersample_to_min(recs, seed=0)
        counts = Counter(r["label"] for r in balanced)
        assert len(set(counts.values())) == 1, f"unequal counts: {counts}"

    def test_minimum_class_unchanged(self):
        recs = _make_records({
            "Urban": ["f1", "f2", "f3", "f4", "f5"],
            "Water": ["f6"],
        })
        balanced = undersample_to_min(recs, seed=0)
        counts = Counter(r["label"] for r in balanced)
        assert counts["Water"] == 1
        assert counts["Urban"] == 1

    def test_deterministic_with_seed(self):
        recs = _make_records({
            "Urban": [f"u{i}" for i in range(10)],
            "Non-urban": ["n1"],
        })
        b1 = undersample_to_min(recs, seed=7)
        b2 = undersample_to_min(recs, seed=7)
        assert [r["img_name"] for r in b1] == [r["img_name"] for r in b2]


class TestSplitByFlight:
    def _multi_flight_records(self) -> list[dict]:
        """10 flights × 3 frames each = 30 records, balanced classes."""
        recs = []
        labels = ["Urban", "Non-urban", "Water"] * 10
        for i in range(10):
            fid = f"flight{i:02d}"
            for j in range(3):
                recs.append({
                    "img_name": f"{fid}_{j}.png",
                    "label": labels[i],
                    "flight_id": fid,
                    "path": f"part1/Images/{fid}/{fid}_{j}.png",
                    "time": str(j),
                    "confidence": 0.9,
                })
        return recs

    def test_flight_disjoint(self):
        recs = self._multi_flight_records()
        splits = split_by_flight(recs, ratios=(0.70, 0.15, 0.15), seed=0)
        all_flights = {
            split_name: {r["flight_id"] for r in subset}
            for split_name, subset in splits.items()
        }
        assert all_flights["train"].isdisjoint(all_flights["val"])
        assert all_flights["train"].isdisjoint(all_flights["test"])
        assert all_flights["val"].isdisjoint(all_flights["test"])

    def test_all_records_assigned(self):
        recs = self._multi_flight_records()
        splits = split_by_flight(recs, ratios=(0.70, 0.15, 0.15), seed=0)
        total = sum(len(v) for v in splits.values())
        assert total == len(recs)

    def test_returns_three_splits(self):
        recs = self._multi_flight_records()
        splits = split_by_flight(recs, ratios=(0.70, 0.15, 0.15), seed=0)
        assert set(splits.keys()) == {"train", "val", "test"}

    def test_deterministic_with_seed(self):
        recs = self._multi_flight_records()
        s1 = split_by_flight(recs, seed=42)
        s2 = split_by_flight(recs, seed=42)
        for k in ("train", "val", "test"):
            assert [r["img_name"] for r in s1[k]] == [r["img_name"] for r in s2[k]]

    def test_custom_ratios_sum_to_one(self):
        recs = self._multi_flight_records()
        # Should not raise even with extreme ratios
        splits = split_by_flight(recs, ratios=(0.8, 0.1, 0.1), seed=0)
        assert all(len(v) >= 0 for v in splits.values())


class TestCropToFramePath:
    def test_strips_crop_suffix(self):
        crop = "part1/Images/abc123/1560848268681abc123_x_1440_y_0.png"
        assert crop_to_frame_path(crop) == "part1/Images/abc123/1560848268681abc123.png"

    def test_multiple_digit_offsets(self):
        crop = "part2/Images/fid/tsfidfid_x_0_y_720.png"
        assert crop_to_frame_path(crop) == "part2/Images/fid/tsfidfid.png"

    def test_no_crop_suffix_unchanged(self):
        path = "part1/Images/fid/timestamp_fid.png"
        assert crop_to_frame_path(path) == "part1/Images/fid/timestamp_fid.png"


class TestParseFramePath:
    def test_roundtrip_with_relative_path(self):
        path = "part1/Images/flight_abc/1234567890flight_abc.png"
        fid, img, part = parse_frame_path(path)
        assert fid == "flight_abc"
        assert img == "1234567890flight_abc.png"
        assert part == "part1"

    def test_part2(self):
        fid, img, part = parse_frame_path("part2/Images/xyz/frame.png")
        assert part == "part2"
        assert fid == "xyz"
        assert img == "frame.png"


class TestLoadDetectionFrameManifest:
    def _write_mini_coco(self, directory: Path, split: str, crops: list[str]) -> None:
        images = [
            {"id": i, "file_name": fn, "width": 960, "height": 960}
            for i, fn in enumerate(crops)
        ]
        coco = {"images": images, "annotations": [], "categories": []}
        with open(directory / f"mini_{split}.json", "w") as f:
            json.dump(coco, f)

    def test_deduplicates_crops_to_frames(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            # Two crops from the same frame
            self._write_mini_coco(d, "train", [
                "part1/Images/f1/ts1f1_x_0_y_0.png",
                "part1/Images/f1/ts1f1_x_960_y_0.png",
            ])
            self._write_mini_coco(d, "eval", [
                "part1/Images/f2/ts2f2_x_0_y_0.png",
            ])
            self._write_mini_coco(d, "test", [
                "part2/Images/f3/ts3f3_x_0_y_0.png",
            ])
            train_manifest = load_detection_frame_manifest(d / "mini_train.json")
            eval_manifest = load_detection_frame_manifest(d / "mini_eval.json")
            test_manifest = load_detection_frame_manifest(d / "mini_test.json")

        assert len(train_manifest) == 1  # deduplicated
        assert train_manifest[0] == "part1/Images/f1/ts1f1.png"
        assert len(eval_manifest) == 1
        assert len(test_manifest) == 1

    def test_returns_all_three_splits(self):
        with tempfile.TemporaryDirectory() as tmp:
            d = Path(tmp)
            for split in ("train", "eval", "test"):
                self._write_mini_coco(d, split, [
                    f"part1/Images/f_{split}/ts_f_{split}_x_0_y_0.png"
                ])
            manifests = {
                split: load_detection_frame_manifest(d / f"mini_{split}.json")
                for split in ("train", "eval", "test")
            }
        assert set(manifests.keys()) == {"train", "eval", "test"}

