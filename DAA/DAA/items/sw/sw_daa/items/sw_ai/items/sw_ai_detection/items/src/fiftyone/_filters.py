from __future__ import annotations

import operator as op
from typing import Any

from fiftyone import ViewField as F

_OPERATORS: dict[str, Any] = {
    ">": op.gt,
    ">=": op.ge,
    "<": op.lt,
    "<=": op.le,
    "==": op.eq,
    "!=": op.ne,
}


def _cast_value(raw: str) -> int | float | str:
    """Best-effort cast of a CLI string to int, float, or leave as str."""
    try:
        return int(raw)
    except ValueError:
        pass
    try:
        return float(raw)
    except ValueError:
        pass
    return raw


def _parse_filter(raw: str) -> tuple[str, str, str]:
    """Split a ``FIELD:OPERATOR:VALUE`` string into its three components.

    Args:
        raw: Raw filter string with format ``FIELD:OPERATOR:VALUE``
            (e.g. ``ground_truth.detections.range_m:==:2000``).

    Raises:
        ValueError: If the string does not contain exactly two ``:`` separators
            or the operator is not recognised.
    """
    parts = raw.split(":", 2)
    if len(parts) != 3:
        raise ValueError(
            f"Invalid filter format: '{raw}'. Expected FIELD:OPERATOR:VALUE "
            f"(e.g. ground_truth.detections.range_m:==:2000)"
        )
    field, operator, value = parts
    if operator not in _OPERATORS:
        raise ValueError(
            f"Unknown operator '{operator}' in filter '{raw}'. Supported: {', '.join(_OPERATORS)}"
        )
    return field, operator, value


def _parse_field_path(field: str) -> tuple[str | None, str]:
    """Split a field path into its detections-field prefix and leaf attribute.

    Args:
        field: Dot-separated field path (e.g. ``ground_truth.detections.range_m``
            or ``video_id``).

    Returns:
        ``(label_field, leaf)`` — *label_field* is the FiftyOne label field
        name (e.g. ``"ground_truth"``) when the path contains
        ``.detections.``, otherwise ``None`` for sample-level fields.
        *leaf* is the attribute name used in the filter expression.
    """
    marker = ".detections."
    idx = field.find(marker)
    if idx != -1:
        return field[:idx], field[idx + len(marker) :]
    return None, field


def _build_filter_expr(field_leaf: str, operator: str, value: int | float | str) -> Any:
    """Build a FiftyOne ``ViewField`` boolean expression for a single comparison.

    Args:
        field_leaf: The leaf attribute name used in the filter expression (e.g. "range_m").
        operator: Comparison operator (e.g. ">", "==", etc.).
        value: The value to compare against.

    Returns:
        A FiftyOne boolean expression that can be used in a view filter.
    """
    vf = F(field_leaf)
    if operator == ">":
        return vf > value
    if operator == ">=":
        return vf >= value
    if operator == "<":
        return vf < value
    if operator == "<=":
        return vf <= value
    if operator == "==":
        return vf == value
    if operator == "!=":
        return vf != value
    raise ValueError(f"Unsupported operator: {operator}")


def _matches_filters(
    det: Any,
    parsed_filters: list[tuple[str, str, int | float | str]],
) -> bool:
    """Check whether a detection matches ALL parsed filters (AND logic).

    Args:
        det: A ``fo.Detection`` instance.
        parsed_filters: List of ``(leaf_attr, operator, cast_value)`` tuples
            produced by parsing ``FIELD:OPERATOR:VALUE`` filter strings.

    Returns:
        ``True`` if every filter passes, ``False`` otherwise.
        A filter is skipped (treated as passing) when the detection does not
        have the attribute — consistent with ``filter_in_imgs_without_attr``.
    """
    for leaf, operator, value in parsed_filters:
        attr_val = det.get_field(leaf)
        if attr_val is None:
            continue
        if not _OPERATORS[operator](attr_val, value):
            return False
    return True


def parse_detection_filters(
    raw_filters: list[str],
) -> list[tuple[str, str, int | float | str]]:
    """Parse a list of ``FIELD:OPERATOR:VALUE`` strings into detection-level filter tuples.

    Strips the ``<label_field>.detections.`` prefix if present so the leaf
    attribute name can be used directly with ``fo.Detection.get_field()``.

    Args:
        raw_filters: List of filter strings (e.g.
            ``["ground_truth.detections.bbox_area:<:200"]``).

    Returns:
        List of ``(leaf_attr, operator, cast_value)`` tuples.
    """
    result = []
    for raw in raw_filters:
        field, operator, value_str = _parse_filter(raw)
        _, leaf = _parse_field_path(field)
        result.append((leaf, operator, _cast_value(value_str)))
    return result
