from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable


@dataclass
class FeatureRoute:
    route_id: str
    feature_group: str
    source_feature_count: int
    length_m: float
    desired_speed_kt: float | None
    points_lla: list[tuple[float, float, float]]


def _import_osm_stack():
    try:
        import geopandas as gpd
        import osmnx as ox
        from shapely.geometry import GeometryCollection, LineString, MultiLineString, MultiPolygon, Polygon
        from shapely.ops import linemerge, substring, unary_union
    except ImportError as exc:
        raise ImportError(
            "This script requires osmnx, geopandas, and shapely. Install them before generating OSM routes."
        ) from exc

    return {
        "gpd": gpd,
        "ox": ox,
        "GeometryCollection": GeometryCollection,
        "LineString": LineString,
        "MultiLineString": MultiLineString,
        "MultiPolygon": MultiPolygon,
        "Polygon": Polygon,
        "linemerge": linemerge,
        "substring": substring,
        "unary_union": unary_union,
    }


def _get_first_value(row: dict[str, Any], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = row.get(key)
        if value is None:
            continue
        if hasattr(value, "item"):
            try:
                value = value.item()
            except Exception:
                pass
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return None


def _get_float_value(row_dict: dict[str, Any], key: str) -> float | None:
    """Return the float value of an OSM attribute, or None if absent or unparseable."""
    val = row_dict.get(key)
    if val is None:
        return None
    try:
        if hasattr(val, "item"):
            val = val.item()
        parsed = float(str(val).strip())
        return parsed if math.isfinite(parsed) else None
    except (ValueError, TypeError):
        return None


def _interpolate_z_from_geometry(geometry: Any, sample_distances: list[float]) -> list[float]:
    """Linearly interpolate Z (elevation) values along a 3D LineString.

    The geometry must be in a projected CRS so distances are in metres.
    Returns one elevation in metres for each entry in sample_distances.
    """
    coords = list(geometry.coords)
    cum_dists: list[float] = [0.0]
    for i in range(1, len(coords)):
        dx = coords[i][0] - coords[i - 1][0]
        dy = coords[i][1] - coords[i - 1][1]
        cum_dists.append(cum_dists[-1] + math.hypot(dx, dy))

    z_vals = [c[2] for c in coords]
    result: list[float] = []
    for dist in sample_distances:
        if dist <= cum_dists[0]:
            result.append(z_vals[0])
            continue
        if dist >= cum_dists[-1]:
            result.append(z_vals[-1])
            continue
        for i in range(1, len(cum_dists)):
            if cum_dists[i] >= dist:
                t = (dist - cum_dists[i - 1]) / (cum_dists[i] - cum_dists[i - 1])
                result.append(z_vals[i - 1] + t * (z_vals[i] - z_vals[i - 1]))
                break
    return result


def _iter_line_geometries(geometry: Any, geometry_types: dict[str, Any]) -> list[Any]:
    LineString = geometry_types["LineString"]
    MultiLineString = geometry_types["MultiLineString"]
    Polygon = geometry_types["Polygon"]
    MultiPolygon = geometry_types["MultiPolygon"]
    GeometryCollection = geometry_types["GeometryCollection"]

    if geometry is None or geometry.is_empty:
        return []
    if isinstance(geometry, LineString):
        return [geometry]
    if isinstance(geometry, MultiLineString):
        return [line for line in geometry.geoms if not line.is_empty]
    if isinstance(geometry, Polygon):
        return _iter_line_geometries(geometry.boundary, geometry_types)
    if isinstance(geometry, MultiPolygon):
        lines = []
        for polygon in geometry.geoms:
            lines.extend(_iter_line_geometries(polygon.boundary, geometry_types))
        return lines
    if isinstance(geometry, GeometryCollection):
        lines = []
        for item in geometry.geoms:
            lines.extend(_iter_line_geometries(item, geometry_types))
        return lines
    return []


def _merge_lines_to_list(lines: list[Any], ops: dict[str, Any]) -> list[Any]:
    if not lines:
        return []

    # Filter out invalid/empty geometries.
    valid_lines = [line for line in lines if line is not None and not line.is_empty]
    if not valid_lines:
        return []

    try:
        # Merge connected line segments.
        unioned = ops["unary_union"](valid_lines)
        if unioned is None or unioned.is_empty:
            return []

        # linemerge tries to join connected segments; it may return a single
        # LineString, a MultiLineString, or the input unchanged if disconnected.
        merged = ops["linemerge"](unioned)

        # Extract individual merged lines; filter out short/invalid ones.
        result = []
        if hasattr(merged, "geoms"):
            # Result is a Multi* type.
            for geom in merged.geoms:
                if geom is not None and not geom.is_empty and getattr(geom, "length", 0.0) > 0.0:
                    result.append(geom)
        elif merged is not None and not merged.is_empty and getattr(merged, "length", 0.0) > 0.0:
            # Result is a single LineString.
            result.append(merged)

        return result
    except Exception as exc:
        # If merging fails, return the valid lines as-is (unmerged).
        return valid_lines


def _split_line_by_min_length(line: Any, min_section_length_m: float, substring_fn: Any) -> list[Any]:
    total_length = float(line.length)
    if total_length < min_section_length_m:
        return []

    section_count = max(1, int(total_length // min_section_length_m))
    target_length = total_length / section_count
    sections = []

    start_distance = 0.0
    for section_index in range(section_count):
        end_distance = total_length if section_index == section_count - 1 else target_length * (section_index + 1)
        segment = substring_fn(line, start_distance, end_distance)
        if getattr(segment, "length", 0.0) > 0.0:
            sections.append(segment)
        start_distance = end_distance

    return sections


def _sample_line_to_lla_points(
    line_gdf: Any,
    spacing_m: float,
    altitude_fallback_m: float,
    altitude_offset_m: float = 0.0,
) -> list[tuple[float, float, float]]:
    """Sample LLA waypoints along a projected LineString.

    Altitude resolution order:
      1. Z coordinates embedded in the geometry (OSM node-level elevations,
         preserved through shapely merge/split operations).
      2. altitude_fallback_m – the feature-level OSM ``ele`` tag value for the
         group, or the user-supplied constant when ``ele`` is absent.
      3. altitude_offset_m is always added on top of whichever source is used
         (useful for specifying a fixed AGL height above the feature elevation).
    """
    geometry = line_gdf.geometry.iloc[0]
    length_m = float(geometry.length)
    sample_distances = [0.0]

    if spacing_m > 0:
        current_distance = spacing_m
        while current_distance < length_m:
            sample_distances.append(current_distance)
            current_distance += spacing_m
    if length_m > 0.0 and sample_distances[-1] != length_m:
        sample_distances.append(length_m)

    sampled_points = [geometry.interpolate(distance) for distance in sample_distances]
    sampled_gdf = line_gdf.__class__({"geometry": sampled_points}, geometry="geometry", crs=line_gdf.crs).to_crs(4326)

    # Prefer Z values embedded in the geometry (from OSM node elevations).
    if getattr(geometry, "has_z", False):
        base_altitudes = _interpolate_z_from_geometry(geometry, sample_distances)
    else:
        base_altitudes = [float(altitude_fallback_m)] * len(sampled_points)

    return [
        (float(point.y), float(point.x), float(alt) + altitude_offset_m)
        for point, alt in zip(sampled_gdf.geometry, base_altitudes)
    ]


def _fetch_features(ox: Any, place_name: str | None, bbox: tuple[float, float, float, float] | None, tags: dict[str, Any]) -> Any:
    if not tags:
        raise ValueError("At least one OSM tag filter must be provided.")

    if place_name:
        if hasattr(ox, "features_from_place"):
            return ox.features_from_place(place_name, tags=tags)
        return ox.geometries_from_place(place_name, tags=tags)

    if bbox is not None:
        north, south, east, west = bbox
        if hasattr(ox, "features_from_bbox"):
            try:
                return ox.features_from_bbox((west, south, east, north), tags=tags)
            except TypeError:
                return ox.features_from_bbox(north=north, south=south, east=east, west=west, tags=tags)
        return ox.geometries_from_bbox(north=north, south=south, east=east, west=west, tags=tags)

    raise ValueError("Either place_name or bbox must be provided.")


def extract_feature_routes(
    *,
    place_name: str | None = None,
    bbox: tuple[float, float, float, float] | None = None,
    tags: dict[str, Any] | None = None,
    min_section_length_m: float = 1000.0,
    point_spacing_m: float = 100.0,
    altitude_m: float = 0.0,
    altitude_offset_m: float = 0.0,
    desired_speed_kt: float | None = None,
    group_by_fields: tuple[str, ...] = ("name", "ref", "waterway", "railway", "highway"),
    route_name_prefix: str = "osm_route",
) -> list[FeatureRoute]:
    
    
    # ---------------------------------------------------------------------------
    # QUICK REFERENCE: OSM Tags
    # ---------------------------------------------------------------------------
    # Tags are passed as a dict[str, str | list[str] | True].
    # Setting a key to True fetches every value for that tag.
    # Multiple keys in the same dict are OR-ed (any feature that has at least
    # one of those keys is returned).
    #
    # Common tag keys and their typical values:
    #
    #   waterway  – river, stream, canal, drain, ditch, brook, tidal_channel
    #   railway   – rail, subway, tram, light_rail, monorail, narrow_gauge,
    #               funicular, disused, abandoned
    #   highway   – motorway, trunk, primary, secondary, tertiary, unclassified,
    #               residential, footway, path, cycleway, bridleway, track
    #   aeroway   – runway, taxiway, apron, helipad, navigationaid
    #   boundary  – administrative, national_park, protected_area, maritime
    #   natural   – coastline, ridge, valley, cliff, wood, water, glacier
    #   landuse   – forest, farmland, residential, industrial, commercial
    #   leisure   – park, nature_reserve, track, pitch
    #   man_made  – pier, pipeline, bridge, embankment, cutline
    #   power     – line, cable, minor_line
    #
    # Examples:
    #   {"waterway": True}                    – all waterways
    #   {"waterway": ["river", "canal"]}      – only rivers and canals
    #   {"railway": True}                     – all railway geometries
    #   {"highway": ["primary", "secondary"]} – primary and secondary roads
    #   {"waterway": True, "railway": True}   – rivers AND railways (OR logic)
    #
    # Full tag reference: https://taginfo.openstreetmap.org/
    #
    # ---------------------------------------------------------------------------
    # AREA SELECTION
    # ---------------------------------------------------------------------------
    # Option A – place_name  (str)
    #     Name resolved by the Nominatim geocoder. Can be a city, region, county,
    #     country, or any recognized OSM place name.
    #     Examples:
    #       "Valencia, Spain"
    #       "Ebro River, Spain"
    #       "Bavaria, Germany"
    #       "Thames, United Kingdom"
    #
    # Option B – bbox  (north, south, east, west)  in decimal degrees
    #     Explicit bounding-box. Useful when you want exact geographic control.
    #     Example: (39.55, 39.30, -0.25, -0.60)  →  Valencia metro area
    #
    # ---------------------------------------------------------------------------
    # OTHER KEY PARAMETERS
    # ---------------------------------------------------------------------------
    # min_section_length_m  (default 1000 m)
    #     After merging connected feature segments, each merged line is split into
    #     sections of AT LEAST this length. Shorter merged lines are discarded.
    #     Increase for longer flight legs; decrease for denser urban areas.
    #
    # point_spacing_m  (default 100 m)
    #     Distance between consecutive LLA waypoints sampled along each section.
    #     Finer values give smoother trajectories; coarser values reduce file size.
    #
    # altitude_m  (default 0.0)
    #     Fallback altitude in metres above the WGS84 ellipsoid.  Elevation is
    #     resolved from OSM in the following priority order:
    #       1. Z coordinates embedded in the OSM way geometry.  Some OSM editors
    #          and imports attach node-level ``ele`` tags, which shapely encodes as
    #          a 3D LineString (x, y, z).  These survive linemerge and substring,
    #          so per-node elevations are interpolated at every sample point.
    #       2. The feature-level OSM ``ele`` tag – a single value for the whole
    #          way, present on bridges, mountain passes, and similar features.
    #          When multiple ways share a feature group the median value is used.
    #       3. This constant fallback, when no OSM elevation is available.
    #
    # altitude_offset_m  (default 0.0)
    #     Metres added on top of whichever altitude source is used above.  Use
    #     this to specify a fixed height above the feature (AGL offset), e.g.
    #     altitude_m=0.0, altitude_offset_m=300.0 means "300 m above whatever
    #     elevation OSM reports (or above sea level if none is found)".
    #
    # desired_speed_kt  (default None)
    #     If provided, stored as metadata on each FeatureRoute.  When the route is
    #     passed to gen_track_from_lla / gen_track, this speed is used for the
    #     simulated trajectory.  None means "unspecified – caller decides."
    #
    # group_by_fields  (default ("name", "ref", "waterway", "railway", "highway"))
    #     Priority-ordered list of OSM attribute keys used to assign a human-
    #     readable name to each feature group before merging.  The first non-empty,
    #     non-NaN value found in these columns is used as the group label.
    #
    # route_name_prefix  (default "osm_route")
    #     String prepended to the four-digit zero-padded route counter in file
    #     names, e.g. "river_route_0001.csv".
    #
    # output_format  ("csv" | "json", default "csv")
    #     CSV  – one file per route, one row per LLA point.
    #     JSON – one file per route, all metadata + points in a single object.
    # ---------------------------------------------------------------------------   
    
    
    osm_stack = _import_osm_stack()
    gpd = osm_stack["gpd"]
    ox = osm_stack["ox"]

    feature_gdf = _fetch_features(ox, place_name, bbox, tags or {})
    if feature_gdf.empty:
        return []

    if feature_gdf.crs is None:
        feature_gdf = feature_gdf.set_crs(4326)

    exploded = feature_gdf.explode(index_parts=False).reset_index(drop=True)
    line_rows = []

    for _, row in exploded.iterrows():
        geometry = row.geometry
        line_geometries = _iter_line_geometries(geometry, osm_stack)
        if not line_geometries:
            continue

        row_dict = row.to_dict()
        feature_group = _get_first_value(row_dict, group_by_fields) or "unnamed_feature"
        # OSM ``ele`` tag: a single elevation in metres for the whole feature way.
        # Common on bridges, mountain passes, and manually-tagged features.
        ele_m = _get_float_value(row_dict, "ele")
        for line_geometry in line_geometries:
            line_rows.append(
                {
                    "feature_group": feature_group,
                    "geometry": line_geometry,
                    "ele_m": ele_m,
                }
            )

    if not line_rows:
        return []

    line_gdf = gpd.GeoDataFrame(line_rows, geometry="geometry", crs=feature_gdf.crs)
    projected_gdf = line_gdf.to_crs(line_gdf.estimate_utm_crs())

    routes: list[FeatureRoute] = []
    route_index = 1

    for feature_group, group_gdf in projected_gdf.groupby("feature_group"):
        # Per-group ele fallback: median of all non-null OSM ``ele`` values in
        # this group, falling back to the user-supplied altitude_m constant.
        ele_values = [v for v in group_gdf["ele_m"] if v is not None and math.isfinite(v)]
        if ele_values:
            sorted_vals = sorted(ele_values)
            mid = len(sorted_vals) // 2
            ele_fallback_m = sorted_vals[mid] if len(sorted_vals) % 2 else (sorted_vals[mid - 1] + sorted_vals[mid]) / 2.0
        else:
            ele_fallback_m = altitude_m

        merged_lines = _merge_lines_to_list(list(group_gdf.geometry), osm_stack)
        for merged_line in merged_lines:
            sections = _split_line_by_min_length(merged_line, min_section_length_m, osm_stack["substring"])
            for section in sections:
                section_gdf = gpd.GeoDataFrame(
                    [{"geometry": section}],
                    geometry="geometry",
                    crs=projected_gdf.crs,
                )
                points_lla = _sample_line_to_lla_points(
                    section_gdf,
                    point_spacing_m,
                    ele_fallback_m,
                    altitude_offset_m=altitude_offset_m,
                )
                if len(points_lla) < 2:
                    continue

                routes.append(
                    FeatureRoute(
                        route_id=f"{route_name_prefix}_{route_index:04d}",
                        feature_group=str(feature_group),
                        source_feature_count=int(len(group_gdf)),
                        length_m=float(section.length),
                        desired_speed_kt=None if desired_speed_kt is None else float(desired_speed_kt),
                        points_lla=points_lla,
                    )
                )
                route_index += 1

    return routes


def save_feature_routes(
    routes: list[FeatureRoute],
    *,
    output_dir: str | Path,
    output_format: str = "csv",
) -> list[Path]:
    output_root = Path(output_dir)
    output_root.mkdir(parents=True, exist_ok=True)
    normalized_format = output_format.lower()

    if normalized_format not in {"csv", "json"}:
        raise ValueError("output_format must be either 'csv' or 'json'.")

    saved_files: list[Path] = []
    for route in routes:
        output_path = output_root / f"{route.route_id}.{normalized_format}"
        if normalized_format == "csv":
            with output_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.writer(csv_file)
                writer.writerow(
                    [
                        "route_id",
                        "feature_group",
                        "point_index",
                        "latitude_deg",
                        "longitude_deg",
                        "altitude_m",
                        "route_length_m",
                        "desired_speed_kt",
                    ]
                )
                for point_index, (latitude_deg, longitude_deg, altitude_m) in enumerate(route.points_lla):
                    writer.writerow(
                        [
                            route.route_id,
                            route.feature_group,
                            point_index,
                            latitude_deg,
                            longitude_deg,
                            altitude_m,
                            route.length_m,
                            route.desired_speed_kt,
                        ]
                    )
        else:
            payload = {
                "route_id": route.route_id,
                "feature_group": route.feature_group,
                "source_feature_count": route.source_feature_count,
                "length_m": route.length_m,
                "desired_speed_kt": route.desired_speed_kt,
                "points_lla": route.points_lla,
            }
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

        saved_files.append(output_path)

    return saved_files


def generate_feature_routes(args: Any = None) -> list[Path]:
    if args is None:
        args = SimpleNamespace()

    tags = getattr(args, "tags", None)
    routes = extract_feature_routes(
        place_name=getattr(args, "place_name", None),
        bbox=getattr(args, "bbox", None),
        tags=tags,
        min_section_length_m=float(getattr(args, "min_section_length_m", 1000.0)),
        point_spacing_m=float(getattr(args, "point_spacing_m", 100.0)),
        altitude_m=float(getattr(args, "altitude_m", 0.0)),
        altitude_offset_m=float(getattr(args, "altitude_offset_m", 0.0)),
        desired_speed_kt=getattr(args, "desired_speed_kt", None),
        route_name_prefix=str(getattr(args, "route_name_prefix", "osm_route")),
    )

    output_dir = getattr(args, "output_dir", None)
    if output_dir is None:
        raise ValueError("output_dir is required to save extracted routes.")

    return save_feature_routes(
        routes,
        output_dir=output_dir,
        output_format=str(getattr(args, "output_format", "csv")),
    )


if __name__ == "__main__":
    raise SystemExit("Use generate_feature_routes(args) from another script or an interactive session.")