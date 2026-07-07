from pathlib import PurePosixPath

from src.preprocessing.dataset_split_random_by_flight import split_random_by_flight


def _flights(split):
    """Extract the set of flight IDs from a COCO split."""
    return {PurePosixPath(img["file_name"]).parent.name for img in split["images"]}


class TestSplitRandomByFlight:
    def test_no_flight_overlap(self, coco):
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.3, seed=42)
        assert _flights(split_a).isdisjoint(_flights(split_b))

    def test_all_images_partitioned(self, coco):
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.2, seed=42)
        total = len(split_a["images"]) + len(split_b["images"])
        assert total == len(coco["images"])

    def test_all_annotations_partitioned(self, coco):
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.2, seed=42)
        total = len(split_a.get("annotations", [])) + len(split_b.get("annotations", []))
        assert total == len(coco["annotations"])

    def test_split_b_is_smaller_than_split_a(self, coco):
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.25, seed=42)
        assert len(_flights(split_b)) < len(_flights(split_a))

    def test_split_b_ratio_approximate(self, coco):
        ratio = 0.3
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=ratio, seed=42)
        n_total = len(_flights(split_a)) + len(_flights(split_b))
        actual = len(_flights(split_b)) / n_total
        assert abs(actual - ratio) < 0.15

    def test_deterministic(self, coco):
        a1, _ = split_random_by_flight(coco, split_b_ratio=0.2, seed=7)
        a2, _ = split_random_by_flight(coco, split_b_ratio=0.2, seed=7)
        assert sorted(i["id"] for i in a1["images"]) == sorted(i["id"] for i in a2["images"])

    def test_videos_match_images(self, coco):
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.2, seed=42)
        for split in (split_a, split_b):
            vid_ids = {img["video_id"] for img in split["images"]}
            split_vid_ids = {v["id"] for v in split.get("videos", [])}
            assert vid_ids == split_vid_ids

    def test_duplicate_flights_same_split(self, coco_factory):
        """Both cameras of the same flight must land in the same split."""
        coco = coco_factory(n_duplicate_flights=2)
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.3, seed=42)
        assert _flights(split_a).isdisjoint(_flights(split_b))

    def test_duplicate_flight_all_images_included(self, coco_factory):
        """All images from both cameras of a duplicated flight are included."""
        coco = coco_factory(n_duplicate_flights=2)
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.3, seed=42)
        total = len(split_a["images"]) + len(split_b["images"])
        assert total == len(coco["images"])

    def test_unannotated_images_preserved(self, coco):
        """Background crops (images without annotations) must not be lost."""
        split_a, split_b = split_random_by_flight(coco, split_b_ratio=0.3, seed=42)

        ann_img_ids = {ann["image_id"] for ann in coco["annotations"]}
        input_unannotated = [img for img in coco["images"] if img["id"] not in ann_img_ids]
        assert len(input_unannotated) > 0, "fixture must include unannotated images"

        a_ann_ids = {ann["image_id"] for ann in split_a.get("annotations", [])}
        b_ann_ids = {ann["image_id"] for ann in split_b.get("annotations", [])}
        output_unannotated = len(
            [img for img in split_a["images"] if img["id"] not in a_ann_ids]
        ) + len([img for img in split_b["images"] if img["id"] not in b_ann_ids])
        assert output_unannotated == len(input_unannotated)
