import argparse
import json
import random
from collections import defaultdict
from typing import Any

from loguru import logger

from src.preprocessing.utils.coco_json_io import load_coco_json, log_coco_stats, save_coco_json
from src.preprocessing.utils.filter_coco import filter_coco_by_image_ids

_SIZE_BINS = ("small", "medium", "large")


_BudgetKey = str | tuple[str, str]


def _available_counts(
    annotations: list[dict[str, Any]],
    cat_id_to_name: dict[int, str],
) -> dict[str, dict[str, int]]:
    """Count annotations per class and size bin.

    Args:
        annotations: COCO annotation dicts with a ``size_category`` field.
        cat_id_to_name: Category ID to name mapping.

    Returns:
        Nested dict ``{class_name: {size_bin: count}}``.
    """
    counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for ann in annotations:
        name = cat_id_to_name.get(ann["category_id"], str(ann["category_id"]))
        size = ann.get("size_category", "unknown")
        if size not in _SIZE_BINS:
            logger.warning(
                f"Annotation {ann.get('id')} has unexpected size_category={size!r} — skipped"
            )
            continue
        counts[name][size] += 1
    return {category_name: dict(size_dict) for category_name, size_dict in counts.items()}


def _log_class_size_table(label: str, counts: dict[str, dict[str, int]]) -> None:
    """Log a per-class × size-bin annotation count table.

    Args:
        label: Header line printed before the table.
        counts: Nested dict ``{class_name: {size_bin: count}}``.
    """
    logger.info(f"{label}:")
    for cls in sorted(counts):
        row = counts[cls]
        total = sum(row.values())
        parts = ", ".join(f"{b}: {row.get(b, 0)}" for b in _SIZE_BINS)
        logger.info(f"  {cls}: {total} total  ({parts})")


def _build_budget(
    targets: dict[str, int | dict[str, int]],
    available: dict[str, dict[str, int]],
) -> dict[_BudgetKey, int]:
    """Convert user targets into a flat budget dict.

    Flat integer values produce a class-level key (``str``).
    Dict values produce per-size keys (``(class, size_bin)`` tuples).

    Args:
        targets: ``{class_name: total_count}`` or
            ``{class_name: {size_bin: count}}``.  Both forms may be mixed.
        available: Available annotation counts from :func:`_available_counts`.

    Returns:
        Budget dict mapping ``str | (class, size_bin)`` to desired count.
    """
    budget: dict[_BudgetKey, int] = {}
    for cls, value in targets.items():
        if isinstance(value, dict):
            for size_bin, count in value.items():
                avail = available.get(cls, {}).get(size_bin, 0)
                if avail <= 0:
                    logger.warning(
                        f"Bucket ({cls}, {size_bin}): target {count} but 0 available — skipped"
                    )
                    continue

                budget[(cls, size_bin)] = min(count, avail)
        else:
            total_count = int(value)
            avail = sum(available.get(cls, {}).values())
            if avail <= 0:
                logger.warning(f"Class {cls!r}: target {total_count} but 0 available — skipped")
                continue

            budget[cls] = min(total_count, avail)
    return budget


def _ann_budget_key(
    ann: dict[str, Any],
    cat_id_to_name: dict[int, str],
    budget: dict[_BudgetKey, int],
) -> _BudgetKey | None:
    """Return the budget key that matches *ann*, or ``None``.

    A ``(class, size_bin)`` key takes priority over a plain class key
    so that per-size budgets are honoured when present.

    Args:
        ann: Single COCO annotation dict.
        cat_id_to_name: Category ID to name mapping.
        budget: Budget dict (used only for key membership checks).

    Returns:
        The matching budget key, or ``None`` if the annotation does not
        belong to any tracked bucket.
    """
    cls = cat_id_to_name.get(ann["category_id"], str(ann["category_id"]))
    size = ann.get("size_category", "unknown")
    key: _BudgetKey = (cls, size)
    if key in budget:
        return key
    if cls in budget:
        return cls
    return None


def _greedy_fill(
    images: list[dict[str, Any]],
    anns_by_image: dict[int, list[dict]],
    cat_id_to_name: dict[int, str],
    budget: dict[_BudgetKey, int],
    rng: random.Random,
) -> set[int]:
    """Greedily select images to fill the global budget.

    Images are shuffled and visited once.  An image is selected when at
    least one of its annotations fills an open budget slot.  **All**
    annotations from a selected image count against the budget to keep
    label sets intact.

    Args:
        images: Annotated image dicts (must have at least one annotation each).
        anns_by_image: Annotations indexed by image ID.
        cat_id_to_name: Category ID to name mapping.
        budget: Desired counts per budget key.
        rng: Seeded RNG for reproducible shuffling.

    Returns:
        Set of selected image IDs.
    """
    remaining = dict(budget)
    images_to_keep: set[int] = set()

    shuffled = list(images)
    rng.shuffle(shuffled)

    for img in shuffled:
        if all(v <= 0 for v in remaining.values()):
            break

        img_id = img["id"]
        anns = anns_by_image.get(img_id, [])
        if not anns:
            continue

        useful = any(
            (key := _ann_budget_key(ann, cat_id_to_name, budget)) is not None
            and remaining.get(key, 0) > 0
            for ann in anns
        )

        if useful:
            images_to_keep.add(img_id)
            for ann in anns:
                key = _ann_budget_key(ann, cat_id_to_name, budget)
                if key is not None:
                    remaining[key] = remaining.get(key, 0) - 1

    return images_to_keep


def sample_coco_dataset(
    coco: dict[str, Any],
    targets: dict[str, int | dict[str, int]],
    seed: int = 42,
    empty_images: int = 0,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Sample images by filling per-class or per-class × size-bin budgets.

    Shuffles all annotated images and greedily selects those whose
    annotations fill open budget slots.  All annotations from a selected
    image are kept intact.

    Args:
        coco: Extended-COCO dict.
        targets: Desired annotation counts.  Accepts either
            ``{class_name: total_count}`` (class-level budget) or
            ``{class_name: {size_bin: count}}`` (per-size budget).
            Both forms may be mixed in the same dict.
        seed: Random seed for reproducibility.
        empty_images: Number of images without annotations to include in the
            sampled output.  Capped at available count.  Defaults to 0.

    Returns:
        Tuple of ``(sampled, remainder)`` where *sampled* contains selected
        images and *remainder* contains everything not selected.
    """
    rng = random.Random(seed)

    images = coco.get("images", [])
    annotations = coco.get("annotations", [])
    cat_id_to_name = {c["id"]: c["name"] for c in coco.get("categories", [])}

    anns_by_image: dict[int, list[dict]] = defaultdict(list)
    for ann in annotations:
        anns_by_image[ann["image_id"]].append(ann)

    annotated_images = [img for img in images if anns_by_image.get(img["id"])]

    available = _available_counts(annotations, cat_id_to_name)
    _log_class_size_table("Available annotations (class × size)", available)

    budget = _build_budget(targets, available)
    kept_ids = _greedy_fill(annotated_images, anns_by_image, cat_id_to_name, budget, rng)

    all_ids = {img["id"] for img in images}

    if empty_images > 0:
        unannotated_ids = [img["id"] for img in images if not anns_by_image.get(img["id"])]
        n_available = len(unannotated_ids)
        n_keep = min(empty_images, n_available)
        rng.shuffle(unannotated_ids)
        kept_ids.update(unannotated_ids[:n_keep])
        logger.info(f"Added {n_keep} empty (unannotated) images to sampled set")

    remainder_ids = all_ids - kept_ids

    sampled = filter_coco_by_image_ids(coco, kept_ids)
    remainder = filter_coco_by_image_ids(coco, remainder_ids)

    out_available = _available_counts(sampled.get("annotations", []), cat_id_to_name)
    logger.info(
        f"Sampled {len(sampled['images'])} images, remainder {len(remainder['images'])} images"
    )
    _log_class_size_table("Output annotations (class × size)", out_available)

    logger.info("Target vs actual:")
    for key in sorted(budget, key=str):
        target_count = budget[key]
        if isinstance(key, tuple):
            cls, size_bin = key
            actual = out_available.get(cls, {}).get(size_bin, 0)
            label = f"({cls}, {size_bin})"
        else:
            actual = sum(out_available.get(key, {}).values())
            label = key
        pct = actual / target_count * 100 if target_count else 0
        if actual < target_count:
            logger.warning(f"  {label}: target {target_count} but got {actual} ({pct:.1f}%)")
        else:
            logger.info(f"  {label}: {actual} / {target_count}  ({pct:.1f}%)")

    return sampled, remainder


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments namespace.
    """
    p = argparse.ArgumentParser(
        description=(
            "Sample a COCO dataset by filling explicit per-class × size-bin buckets. "
            "Images are drawn proportionally from each video."
        ),
    )
    p.add_argument("--input-json", required=True, help="Path to input COCO JSON.")
    p.add_argument("--output-json", required=True, help="Path for the output COCO JSON.")
    p.add_argument(
        "--targets",
        required=True,
        help=(
            "JSON file path or inline JSON string with "
            "{class_name: {size_bin: count}} or {class_name: total_count}. "
            "Example: '{\"airplane\": 5000}' or "
            '\'{"airplane": {"small": 5000, "medium": 2000, "large": 500}}\''
        ),
    )
    p.add_argument("--remainder-json", default=None, help="Output path for non-selected images.")
    p.add_argument(
        "--empty-images",
        type=int,
        default=0,
        help="Number of images without annotations to include in the sampled output.",
    )
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    coco = load_coco_json(args.input_json)

    targets = json.loads(args.targets)

    log_coco_stats(coco, "Loaded")
    logger.info(f"Bucket targets: {targets}")

    sampled, remainder = sample_coco_dataset(
        coco,
        targets=targets,
        seed=args.seed,
        empty_images=args.empty_images,
    )

    for path, data, label in [
        (args.output_json, sampled, "sampled"),
        (args.remainder_json, remainder, "remainder"),
    ]:
        if path is not None:
            save_coco_json(data, path)
            logger.info(f"Written {label} -> {path}")


if __name__ == "__main__":
    main()
