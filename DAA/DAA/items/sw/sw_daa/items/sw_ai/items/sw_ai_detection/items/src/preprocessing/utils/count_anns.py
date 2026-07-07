from typing import Any


def count_anns_by_class(coco: dict[str, Any]) -> dict[str, int]:
    """Count annotations per class name.

    Args:
        coco: COCO dict with ``annotations`` and ``categories``.

    Returns:
        ``{class_name: count}``.
    """
    cat_id_to_name = {c["id"]: c["name"] for c in coco.get("categories", [])}
    counts: dict[str, int] = {}
    for ann in coco.get("annotations", []):
        name = cat_id_to_name.get(ann["category_id"], str(ann["category_id"]))
        counts[name] = counts.get(name, 0) + 1
    return counts
