import argparse
import random
from collections import defaultdict
from pathlib import PurePosixPath
from typing import Any

from loguru import logger

from src.preprocessing.utils.coco_json_io import load_coco_json, log_coco_stats, save_coco_json
from src.preprocessing.utils.count_anns import count_anns_by_class
from src.preprocessing.utils.filter_coco import filter_coco_by_image_ids


def _flight_id_from_filename(file_name: str) -> str:
    """Extract the flight identifier from an image ``file_name``.

    The Airborne dataset stores frames under
    ``<part>/Images/<flight_id>/<timestamp>.png``.  The flight_id (folder name)
    is shared across cameras of the same encounter — even when they appear in
    different parts with different ``video_id`` values.

    Args:
        file_name: Image ``file_name`` field from COCO JSON.

    Returns:
        The flight identifier string.
    """
    return PurePosixPath(file_name).parent.name


def _per_flight_class_counts(
    annotations: list[dict[str, Any]],
    image_id_to_flight: dict[int, str],
) -> dict[str, dict[int, int]]:
    """Count annotations per flight and category.

    Args:
        annotations: List of COCO annotation dicts.
        image_id_to_flight: Mapping from image ID to flight ID.

    Returns:
        ``{flight_id: {category_id: count}}``.
    """
    stats: dict[str, dict[int, int]] = defaultdict(lambda: defaultdict(int))
    for ann in annotations:
        fid = image_id_to_flight.get(ann["image_id"])
        if fid is not None:
            stats[fid][ann["category_id"]] += 1
    return stats


def _img_ids(images_by_flight: dict[str, list[dict[str, Any]]], flights: set[str]) -> set[int]:
    """Collect all image IDs belonging to the given flight IDs.

    Args:
        images_by_flight: Images grouped by flight ID.
        flights: Flight IDs to collect images for.

    Returns:
        Set of image IDs.
    """
    ids: set[int] = set()
    for fid in flights:
        for img in images_by_flight.get(fid, []):
            ids.add(img["id"])
    return ids


def _balanced_class_flight_split(
    flight_ids: list[str],
    flight_class_counts: dict[str, dict[int, int]],
    all_cat_ids: set[int],
    split_b_ratio: float,
    rng: random.Random,
) -> tuple[set[str], set[str]]:
    """Assign flights to two splits while balancing per-class annotation counts.

    Uses a greedy strategy: shuffle flights then assign each to the split
    with the largest normalised deficit relative to its target share.

    Args:
        flight_ids: All flight IDs to assign.
        flight_class_counts: Annotation counts ``{flight_id: {category_id: count}}``.
        all_cat_ids: Complete set of category IDs.
        split_b_ratio: Target fraction of flights for split B.
        rng: Seeded RNG for reproducible shuffling.

    Returns:
        Tuple of ``(split_a_flight_ids, split_b_flight_ids)``.
    """
    ids = list(flight_ids)
    rng.shuffle(ids)

    n_split_b = round(len(ids) * split_b_ratio)

    total: dict[int, int] = defaultdict(int)
    for fid in ids:
        for cat, n in flight_class_counts.get(fid, {}).items():
            total[cat] += n

    target_split_a = {c: max(1, n * (1.0 - split_b_ratio)) for c, n in total.items()}
    target_split_b = {c: max(1, n * split_b_ratio) for c, n in total.items()}

    split_a_ids: set[str] = set()
    split_b_ids: set[str] = set()
    split_a_counts: dict[int, int] = defaultdict(int)
    split_b_counts: dict[int, int] = defaultdict(int)

    for fid in ids:
        split_a_deficit = sum(
            max(0.0, 1.0 - split_a_counts[c] / target_split_a[c])
            for c in all_cat_ids
            if target_split_a.get(c, 0) > 0
        )
        split_b_deficit = sum(
            max(0.0, 1.0 - split_b_counts[c] / target_split_b[c])
            for c in all_cat_ids
            if target_split_b.get(c, 0) > 0
        )
        counts = flight_class_counts.get(fid, {})

        if split_b_deficit >= split_a_deficit and len(split_b_ids) < n_split_b:
            split_b_ids.add(fid)
            for c, n in counts.items():
                split_b_counts[c] += n
        else:
            split_a_ids.add(fid)
            for c, n in counts.items():
                split_a_counts[c] += n

    return split_a_ids, split_b_ids


def split_random_by_flight(
    coco: dict[str, Any],
    split_b_ratio: float = 0.2,
    seed: int = 42,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split a COCO dataset into two splits at the flight level with no overlap.

    A *flight* is identified by the folder name in each image's ``file_name``
    (e.g. ``part1/Images/<flight_id>/frame.png``).  Multiple cameras
    (video IDs) from the same flight always land in the same split, preventing
    data leakage between train and eval.

    Flights are assigned using a stratified greedy algorithm that balances
    per-class annotation counts between splits.

    Args:
        coco: COCO dict with ``videos`` and ``tracks`` extensions.
        split_b_ratio: Fraction of flights assigned to split B. Default 0.2.
        seed: Random seed for reproducibility.

    Returns:
        Tuple of ``(split_a_coco, split_b_coco)``.
    """
    rng = random.Random(seed)

    images = coco.get("images", [])
    annotations = coco.get("annotations", [])
    all_cat_ids = {c["id"] for c in coco.get("categories", [])}

    image_id_to_flight: dict[int, str] = {}
    images_by_flight: dict[str, list[dict]] = defaultdict(list)
    for img in images:
        fid = _flight_id_from_filename(img["file_name"])
        image_id_to_flight[img["id"]] = fid
        images_by_flight[fid].append(img)

    all_flight_ids = sorted(images_by_flight.keys())
    flight_class_counts = _per_flight_class_counts(annotations, image_id_to_flight)

    split_a_flight_ids, split_b_flight_ids = _balanced_class_flight_split(
        all_flight_ids,
        flight_class_counts,
        all_cat_ids,
        split_b_ratio,
        rng,
    )

    split_a_img_ids = _img_ids(images_by_flight, split_a_flight_ids)
    split_b_img_ids = _img_ids(images_by_flight, split_b_flight_ids)

    split_a = filter_coco_by_image_ids(coco, split_a_img_ids)
    split_b = filter_coco_by_image_ids(coco, split_b_img_ids)

    logger.info(
        f"Split A: {len(split_a['images'])} images, "
        f"{len(split_a.get('annotations', []))} annotations, "
        f"{len(split_a.get('videos', []))} videos, "
        f"{len(split_a_flight_ids)} flights — {count_anns_by_class(split_a)}"
    )
    logger.info(
        f"Split B: {len(split_b['images'])} images, "
        f"{len(split_b.get('annotations', []))} annotations, "
        f"{len(split_b.get('videos', []))} videos, "
        f"{len(split_b_flight_ids)} flights — {count_anns_by_class(split_b)}"
    )

    return split_a, split_b


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    p = argparse.ArgumentParser(
        description="Split a COCO dataset into two splits by flight (no flight overlap).",
    )
    p.add_argument("--input-json", required=True, help="Path to input COCO JSON.")
    p.add_argument("--split-a-json", required=True, help="Output path for split A.")
    p.add_argument("--split-b-json", required=True, help="Output path for split B.")
    p.add_argument(
        "--split-b-ratio",
        type=float,
        default=0.2,
        help="Fraction of videos assigned to split B. Default: 0.2",
    )
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    coco = load_coco_json(args.input_json)
    log_coco_stats(coco, "Loaded")

    split_a, split_b = split_random_by_flight(
        coco,
        split_b_ratio=args.split_b_ratio,
        seed=args.seed,
    )

    for path, data, label in [
        (args.split_a_json, split_a, "split A"),
        (args.split_b_json, split_b, "split B"),
    ]:
        save_coco_json(data, path)
        logger.info(f"Wrote {label} -> {path}")


if __name__ == "__main__":
    main()
