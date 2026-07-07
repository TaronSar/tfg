from __future__ import annotations

import math
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from generate_osm_feature_routes import FeatureRoute, save_feature_routes

EARTH_RADIUS_M = 6378137.0


def _xy_to_lla(center_lat_deg: float, center_lon_deg: float, east_m: float, north_m: float, altitude_m: float) -> tuple[float, float, float]:
    lat0_rad = math.radians(center_lat_deg)
    lat_deg = center_lat_deg + (north_m / EARTH_RADIUS_M) * (180.0 / math.pi)
    lon_deg = center_lon_deg + (east_m / (EARTH_RADIUS_M * max(math.cos(lat0_rad), 1e-9))) * (180.0 / math.pi)
    return lat_deg, lon_deg, altitude_m


def _polyline_length_m(points_xy: list[tuple[float, float]]) -> float:
    if len(points_xy) < 2:
        return 0.0
    total = 0.0
    for i in range(1, len(points_xy)):
        de = points_xy[i][0] - points_xy[i - 1][0]
        dn = points_xy[i][1] - points_xy[i - 1][1]
        total += math.hypot(de, dn)
    return total


def _densify_polyline(points_xy: list[tuple[float, float]], spacing_m: float) -> list[tuple[float, float]]:
    if len(points_xy) < 2:
        return points_xy

    spacing = max(1.0, float(spacing_m))
    dense: list[tuple[float, float]] = [points_xy[0]]

    for i in range(1, len(points_xy)):
        start = points_xy[i - 1]
        end = points_xy[i]
        de = end[0] - start[0]
        dn = end[1] - start[1]
        seg_len = math.hypot(de, dn)
        if seg_len < 1e-9:
            continue

        steps = max(1, int(seg_len // spacing))
        for k in range(1, steps + 1):
            t = min(1.0, (k * spacing) / seg_len)
            dense.append((start[0] + t * de, start[1] + t * dn))
        if dense[-1] != end:
            dense.append(end)

    return dense


def _build_circular_xy(radius_m: float, loops: int, point_spacing_m: float = 50.0, start_bearing_deg: float = 0.0, clockwise: bool = True) -> list[tuple[float, float]]:
    radius = max(1.0, float(radius_m))
    loop_count = max(1, int(loops))
    circumference = 2.0 * math.pi * radius
    points_per_loop = max(16, int(circumference / max(point_spacing_m, 1.0)))
    total_points = points_per_loop * loop_count

    start_rad = math.radians(float(start_bearing_deg))
    sign = -1.0 if clockwise else 1.0

    points: list[tuple[float, float]] = []
    for i in range(total_points + 1):
        angle = start_rad + sign * (2.0 * math.pi * i / points_per_loop)
        east = radius * math.sin(angle)
        north = radius * math.cos(angle)
        points.append((east, north))
    return points


def _build_parallel_xy(leg_length_m: float, leg_spacing_m: float, leg_count: int, heading_deg: float, point_spacing_m: float = 50.0) -> list[tuple[float, float]]:
    length = max(1.0, float(leg_length_m))
    spacing = max(1.0, float(leg_spacing_m))
    count = max(2, int(leg_count))

    # Build in local frame (x=east, y=north) then rotate by heading.
    points_local: list[tuple[float, float]] = [(0.0, 0.0)]
    direction = 1.0
    y = 0.0

    for i in range(count):
        x_target = length if direction > 0 else 0.0
        points_local.append((x_target, y))
        if i < count - 1:
            y += spacing
            points_local.append((x_target, y))
        direction *= -1.0

    heading = math.radians(float(heading_deg))
    cos_h = math.cos(heading)
    sin_h = math.sin(heading)

    points_rotated = [
        (x * cos_h - y * sin_h, x * sin_h + y * cos_h)
        for x, y in points_local
    ]
    return _densify_polyline(points_rotated, point_spacing_m)


def _build_sector_xy(radius_m: float, sector_count: int, clockwise: bool, point_spacing_m: float = 50.0) -> list[tuple[float, float]]:
    radius = max(1.0, float(radius_m))
    count = 2 * max(2, int(sector_count))
    sign = -1.0 if clockwise else 1.0

    # Triangular sector sweeps around the search center:
    # center -> perimeter point A -> adjacent perimeter point B -> center.
    boundary_points: list[tuple[float, float]] = []
    for i in range(count):
        angle = sign * (2.0 * math.pi * i / count)
        east = radius * math.sin(angle)
        north = radius * math.cos(angle)
        boundary_points.append((east, north))

    points: list[tuple[float, float]] = [(0.0, 0.0)]
    for i in range(round(count / 2)):
        a = boundary_points[2 * i]
        b = boundary_points[(2 * i + 1) % count]
        points.extend([a, b, (0.0, 0.0)])

    return _densify_polyline(points, point_spacing_m)


def _build_expanding_square_xy(initial_leg_m: float, leg_increment_m: float, leg_count: int, heading_deg: float, clockwise: bool, point_spacing_m: float = 50.0) -> list[tuple[float, float]]:
    length = max(1.0, float(initial_leg_m))
    increment = max(0.1, float(leg_increment_m))
    count = max(4, int(leg_count))

    # Directions in local XY: N, E, S, W (counter-clockwise order adjusted by clockwise flag).
    dirs_ccw = [(0.0, 1.0), (1.0, 0.0), (0.0, -1.0), (-1.0, 0.0)]
    dirs_cw = [(0.0, 1.0), (-1.0, 0.0), (0.0, -1.0), (1.0, 0.0)]
    dirs = dirs_cw if clockwise else dirs_ccw

    points_local: list[tuple[float, float]] = [(0.0, 0.0)]
    x = 0.0
    y = 0.0
    current_len = length

    for i in range(count):
        dx, dy = dirs[i % 4]
        x += dx * current_len
        y += dy * current_len
        points_local.append((x, y))

        # Increase every two legs for expanding square geometry.
        if i % 2 == 1:
            current_len += increment

    heading = math.radians(float(heading_deg))
    cos_h = math.cos(heading)
    sin_h = math.sin(heading)
    points_rotated = [
        (x * cos_h - y * sin_h, x * sin_h + y * cos_h)
        for x, y in points_local
    ]
    return _densify_polyline(points_rotated, point_spacing_m)


def generate_search_pattern_route(
    *,
    pattern_type: str,
    center_lat_deg: float,
    center_lon_deg: float,
    altitude_m: float = 0.0,
    desired_speed_kt: float | None = None,
    route_id: str = "search_pattern_0001",
    feature_group: str | None = None,
    point_spacing_m: float = 100.0,
    radius_m: float = 1000.0,
    loops: int = 1,
    start_bearing_deg: float = 0.0,
    clockwise: bool = False,
    leg_length_m: float = 1000.0,
    leg_spacing_m: float = 300.0,
    leg_count: int = 6,
    heading_deg: float = 0.0,
    sector_count: int = 6,
    initial_leg_m: float = 300.0,
    leg_increment_m: float = 300.0,
) -> FeatureRoute:
    pattern = pattern_type.strip().lower()

    if pattern == "circular":
        points_xy = _build_circular_xy(radius_m, loops, point_spacing_m, start_bearing_deg, clockwise)
    elif pattern in {"parallel", "parallel_path"}:
        points_xy = _build_parallel_xy(leg_length_m, leg_spacing_m, leg_count, heading_deg, point_spacing_m)
    elif pattern == "sector":
        points_xy = _build_sector_xy(radius_m, sector_count, clockwise, point_spacing_m)
    elif pattern in {"expanding_square", "square"}:
        points_xy = _build_expanding_square_xy(initial_leg_m, leg_increment_m, leg_count, heading_deg, clockwise, point_spacing_m)
    else:
        raise ValueError(
            "pattern_type must be one of: circular, parallel, sector, expanding_square"
        )

    points_lla = [
        _xy_to_lla(center_lat_deg, center_lon_deg, east_m, north_m, float(altitude_m))
        for east_m, north_m in points_xy
    ]

    return FeatureRoute(
        route_id=route_id,
        feature_group=feature_group or f"search_pattern:{pattern}",
        source_feature_count=1,
        length_m=_polyline_length_m(points_xy),
        desired_speed_kt=None if desired_speed_kt is None else float(desired_speed_kt),
        points_lla=points_lla,
    )


def save_search_pattern_route(
    route: FeatureRoute,
    *,
    output_dir: str | Path,
    output_format: str = "csv",
) -> Path:
    return save_feature_routes([route], output_dir=output_dir, output_format=output_format)[0]


def generate_search_pattern_routes(args: Any = None) -> list[Path]:
    if args is None:
        args = SimpleNamespace()

    route = generate_search_pattern_route(
        pattern_type=getattr(args, "pattern_type", "circular"),
        center_lat_deg=float(getattr(args, "center_lat_deg", 39.4699)),
        center_lon_deg=float(getattr(args, "center_lon_deg", -0.3763)),
        altitude_m=float(getattr(args, "altitude_m", 300.0)),
        desired_speed_kt=getattr(args, "desired_speed_kt", None),
        route_id=getattr(args, "route_id", "search_pattern_0001"),
        feature_group=getattr(args, "feature_group", None),
        point_spacing_m=float(getattr(args, "point_spacing_m", 100.0)),
        radius_m=float(getattr(args, "radius_m", 1000.0)),
        loops=int(getattr(args, "loops", 1)),
        start_bearing_deg=float(getattr(args, "start_bearing_deg", 0.0)),
        clockwise=bool(getattr(args, "clockwise", False)),
        leg_length_m=float(getattr(args, "leg_length_m", 1000.0)),
        leg_spacing_m=float(getattr(args, "leg_spacing_m", 300.0)),
        leg_count=int(getattr(args, "leg_count", 6)),
        heading_deg=float(getattr(args, "heading_deg", 0.0)),
        sector_count=int(getattr(args, "sector_count", 6)),
        initial_leg_m=float(getattr(args, "initial_leg_m", 300.0)),
        leg_increment_m=float(getattr(args, "leg_increment_m", 300.0)),
    )

    output_dir = Path(getattr(args, "output_dir", Path(__file__).parent.parent / "examples" / "search_patterns"))
    output_format = str(getattr(args, "output_format", "csv"))
    return save_feature_routes([route], output_dir=output_dir, output_format=output_format)


if __name__ == "__main__":
    generate_search_pattern_routes()
