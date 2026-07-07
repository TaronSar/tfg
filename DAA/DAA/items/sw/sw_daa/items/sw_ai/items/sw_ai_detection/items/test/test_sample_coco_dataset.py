from src.preprocessing.sample_coco_dataset import sample_coco_dataset

_TARGETS = {
    "airplane": {"small": 2, "medium": 2, "large": 2},
    "helicopter": {"small": 2, "medium": 2, "large": 2},
    "bird": {"small": 2, "medium": 2, "large": 2},
}


class TestSampleCocoDataset:
    def test_returns_two_dicts(self, coco):
        sampled, remainder = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        assert isinstance(sampled, dict) and isinstance(remainder, dict)

    def test_partitions_all_images(self, coco):
        sampled, remainder = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        all_ids = {img["id"] for img in coco["images"]}
        sampled_ids = {img["id"] for img in sampled["images"]}
        remainder_ids = {img["id"] for img in remainder["images"]}
        assert sampled_ids | remainder_ids == all_ids
        assert sampled_ids.isdisjoint(remainder_ids)

    def test_reduces_image_count(self, coco):
        sampled, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        assert len(sampled["images"]) < len(coco["images"])

    def test_all_annotations_partitioned(self, coco):
        sampled, remainder = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        total = len(sampled.get("annotations", [])) + len(remainder.get("annotations", []))
        assert total == len(coco["annotations"])

    def test_annotations_belong_to_their_split_images(self, coco):
        sampled, remainder = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        for split in (sampled, remainder):
            img_ids = {img["id"] for img in split["images"]}
            for ann in split.get("annotations", []):
                assert ann["image_id"] in img_ids

    def test_all_annotations_of_selected_image_stay_in_sampled(self, coco):
        sampled, remainder = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        sampled_img_ids = {img["id"] for img in sampled["images"]}
        remainder_ann_img_ids = {a["image_id"] for a in remainder.get("annotations", [])}
        assert sampled_img_ids.isdisjoint(remainder_ann_img_ids)

    def test_deterministic(self, coco):
        s1, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=7)
        s2, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=7)
        assert sorted(i["id"] for i in s1["images"]) == sorted(i["id"] for i in s2["images"])

    def test_video_diversity_preserved(self, coco):
        sampled, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        video_ids = {img["video_id"] for img in sampled["images"] if "video_id" in img}
        assert len(video_ids) > 1

    def test_videos_match_images(self, coco):
        sampled, remainder = sample_coco_dataset(coco, targets=_TARGETS, seed=42)
        for split in (sampled, remainder):
            vid_ids = {img["video_id"] for img in split["images"] if "video_id" in img}
            split_vid_ids = {v["id"] for v in split.get("videos", [])}
            assert vid_ids == split_vid_ids

    def test_target_exceeding_available_keeps_all(self, coco_factory):
        coco = coco_factory(parts=[("part1", 1)], frames_per_video=4, ann_every=1)
        large_targets = {
            "airplane": {"small": 999, "medium": 999, "large": 999},
            "helicopter": {"small": 999, "medium": 999, "large": 999},
            "bird": {"small": 999, "medium": 999, "large": 999},
        }
        sampled, _ = sample_coco_dataset(coco, targets=large_targets, seed=42)
        annotated_ids = {a["image_id"] for a in coco["annotations"]}
        sampled_ids = {img["id"] for img in sampled["images"]}
        assert annotated_ids <= sampled_ids


class TestEmptyImages:
    """Tests for the ``empty_images`` parameter."""

    def test_empty_images_included(self, coco):
        sampled, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=42, empty_images=5)
        ann_img_ids = {ann["image_id"] for ann in sampled["annotations"]}
        unannotated = [img for img in sampled["images"] if img["id"] not in ann_img_ids]
        assert len(unannotated) >= 1

    def test_empty_images_count(self, coco):
        n_empty = 3
        sampled, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=42, empty_images=n_empty)
        ann_img_ids = {ann["image_id"] for ann in sampled["annotations"]}
        unannotated = [img for img in sampled["images"] if img["id"] not in ann_img_ids]
        assert len(unannotated) == n_empty

    def test_empty_images_capped_at_available(self, coco):
        """Requesting more empty images than available should not error."""
        sampled, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=42, empty_images=999999)
        ann_img_ids = {ann["image_id"] for ann in coco["annotations"]}
        total_unannotated = sum(1 for img in coco["images"] if img["id"] not in ann_img_ids)
        result_ann_ids = {ann["image_id"] for ann in sampled["annotations"]}
        result_unannotated = sum(1 for img in sampled["images"] if img["id"] not in result_ann_ids)
        assert result_unannotated == total_unannotated

    def test_zero_empty_images_no_unannotated(self, coco):
        sampled, _ = sample_coco_dataset(coco, targets=_TARGETS, seed=42, empty_images=0)
        ann_img_ids = {ann["image_id"] for ann in sampled["annotations"]}
        unannotated = [img for img in sampled["images"] if img["id"] not in ann_img_ids]
        assert len(unannotated) == 0
