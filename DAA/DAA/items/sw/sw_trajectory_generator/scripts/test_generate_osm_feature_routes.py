"""
Test / demonstration script for generate_osm_feature_routes.py.

Requires: osmnx, geopandas, shapely.
Install:   pip install osmnx geopandas shapely

Run (from the scripts/ directory):
    python test_generate_osm_feature_routes.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from .generate_osm_feature_routes import extract_feature_routes, save_feature_routes, generate_feature_routes


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
#     Constant altitude (metres above WGS84 ellipsoid) assigned to every LLA
#     point.  Terrain-following or variable altitudes are not yet computed here.
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


def example_rivers_by_place():
    """Extract river sections around Valencia, Spain and save as CSV."""
    print("\n--- Example 1: rivers by place name (CSV output) ---")

    routes = extract_feature_routes(
        # Resolved by the OSM Nominatim geocoder.
        place_name="Valencia, Spain",

        # Fetch all OSM features tagged with 'waterway = river'.
        # Use True to fetch every value, or a list for specific values.
        tags={"waterway": ["river", "canal"]},

        # Each route section must be at least 2 km long.
        min_section_length_m=15000.0,

        # Sample a waypoint every 200 m along each section.
        point_spacing_m=200.0,

        # Altitude above ellipsoid (m) – constant for the whole route.
        altitude_m=300.0,

        # Speed metadata stored with each route; not used until you call
        # gen_track_from_lla with this speed.
        desired_speed_kt=80.0,

        # Files will be named "river_0001.csv", "river_0002.csv", …
        route_name_prefix="river",
    )

    if not routes:
        print("  No routes found – check internet connectivity and the place name.")
        return

    output_dir = Path(__file__).parent.parent / "examples" / "osm" / "osm_rivers"
    saved = save_feature_routes(routes, output_dir=output_dir, output_format="csv")

    print(f"  {len(routes)} route section(s) extracted.")
    for route in routes[:3]:
        print(
            f"  {route.route_id}  group='{route.feature_group}'  "
            f"length={route.length_m:.0f} m  points={len(route.points_lla)}"
        )
    print(f"  Saved {len(saved)} file(s) to: {output_dir}")


def example_railways_by_bbox():
    """Extract railway sections using an explicit bounding box and save as CSV."""
    print("\n--- Example 2: railways by bounding box (CSV output) ---")

    # Bounding box: (north, south, east, west) in decimal degrees.
    # This box covers a region near Valencia, Spain.
    valencia_bbox = (39.55, 39.30, -0.25, -0.60)

    routes = extract_feature_routes(
        bbox=valencia_bbox,

        # Fetch all OSM features tagged with any railway key value.
        tags={"railway": True},

        # Only keep sections that are at least 1 km long.
        min_section_length_m=15000.0,

        # Denser waypoint sampling for railway geometry fidelity.
        point_spacing_m=50.0,

        altitude_m=100.0,
        desired_speed_kt=120.0,
        route_name_prefix="railway",
    )

    if not routes:
        print("  No routes found – check internet connectivity and the bounding box.")
        return

    output_dir = Path(__file__).parent.parent / "examples" / "osm" / "osm_railways"
    saved = save_feature_routes(routes, output_dir=output_dir, output_format="csv")

    print(f"  {len(routes)} route section(s) extracted.")
    for route in routes[:3]:
        print(
            f"  {route.route_id}  group='{route.feature_group}'  "
            f"length={route.length_m:.0f} m  points={len(route.points_lla)}"
        )
    print(f"  Saved {len(saved)} file(s) to: {output_dir}")


def example_multiple_tags():
    """Extract both rivers and roads in the same call (OR logic across tags)."""
    print("\n--- Example 3: rivers and primary roads combined ---")

    routes = extract_feature_routes(
        place_name="Zaragoza, Spain",

        # Both waterway and highway features are returned.  OSMnx ORs the tags.
        tags={"waterway": ["river"], "highway": ["primary", "trunk"]},

        min_section_length_m=15000.0,
        point_spacing_m=300.0,
        altitude_m=200.0,
        desired_speed_kt=150.0,
        route_name_prefix="mixed",

        # Prefer 'name' and 'ref' labels before falling back to tag key name.
        group_by_fields=("name", "ref", "waterway", "highway"),
    )

    if not routes:
        print("  No routes found.")
        return

    output_dir = Path(__file__).parent.parent / "examples" / "osm" / "osm_mixed"
    saved = save_feature_routes(routes, output_dir=output_dir, output_format="csv")

    print(f"  {len(routes)} route section(s) extracted.")
    for route in routes[:3]:
        print(
            f"  {route.route_id}  group='{route.feature_group}'  "
            f"length={route.length_m:.0f} m  points={len(route.points_lla)}"
        )
    print(f"  Saved {len(saved)} file(s) to: {output_dir}")


def example_via_main():
    """Show how to drive the module through the generate_feature_routes(args) entry point."""
    print("\n--- Example 4: via generate_feature_routes(args) SimpleNamespace interface ---")

    args = SimpleNamespace(
        # Area selection (use place_name OR bbox, not both).
        # Using a bounding box instead of a river name, which Nominatim
        # may not geocode to a polygon.
        place_name=None,
        bbox=(41.40, 41.35, 2.25, 2.15),  # Barcelona area

        # OSM tag filter – large waterways only.
        tags={"waterway": ["river", "stream"]},

        # Sectioning and sampling parameters.
        min_section_length_m=6000.0,
        point_spacing_m=300.0,

        # Flight parameters.
        altitude_m=200.0,
        desired_speed_kt=110.0,

        # Output.
        output_dir=str(Path(__file__).parent.parent / "examples" / "osm" / "osm_barcelona_rivers"),
        output_format="csv",
        route_name_prefix="barcelona_river",
    )

    saved = generate_feature_routes(args)
    print(f"  Saved {len(saved)} file(s) to: {args.output_dir}")


def main_test():
    examples = [
        example_rivers_by_place,
        example_railways_by_bbox,
        example_multiple_tags,
        example_via_main,
    ]

    print("Running OSM feature route generation examples.")
    print("Each example downloads live data from OpenStreetMap.")

    for fn in examples:
        try:
            fn()
        except ImportError as exc:
            print(f"\n  [SKIP] {fn.__name__}: {exc}")
        except Exception as exc:
            print(f"\n  [ERROR] {fn.__name__}: {exc}")

    print("\nDone.")


if __name__ == "__main__":
    main_test()
