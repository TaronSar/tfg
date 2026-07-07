"""
Test / demonstration script for generate_search_pattern_routes.py.

Generates four adjustable search patterns and saves each as CSV with the same
column format used by OSM-generated route files.
"""

from __future__ import annotations

from pathlib import Path

from .generate_search_pattern_routes import generate_search_pattern_route, save_search_pattern_route
from .generate_encounters import generate_single_encounter


def _run_example(route):
    output_dir = Path(__file__).parent.parent / "examples" / "search_patterns"
    saved_path = save_search_pattern_route(route, output_dir=output_dir, output_format="csv")
    print(
        f"{route.feature_group}: id={route.route_id}, points={len(route.points_lla)}, "
        f"length_m={route.length_m:.1f}, file={saved_path}"
    )
    param_spec = {
        "Ownship_speed": 80,
        "Ownship_altitude": 400,
        "Ownship_altitude_end": 400,
        "Ownship_category": "HB10",
        "Ownship_straight_line": False,
        "Intruder_speed": float(route.desired_speed_kt),
        "Intruder_altitude": 400,
        "Intruder_altitude_end": 400,
        "Intruder_trajectory_csv_filename": str(saved_path),
        "Intruder_azimuth": 225,
        "Intruder_lateral_offset": 1000,
        "Intruder_vertical_offset": 0,
        "Intruder_straight_line": False,
        "flight_duration": 240,
        "seed": True,
    }
    generate_single_encounter(param_spec, return_mode="plot")


def run_search_pattern_routes_demo():

    route = generate_search_pattern_route(
        pattern_type="circular",
        route_id="search_circular_0001",
        center_lat_deg=39.4699,
        center_lon_deg=-0.3763,
        altitude_m=350.0,
        desired_speed_kt=90.0,
        radius_m=1200.0,
        loops=2,
        start_bearing_deg=15.0,
        clockwise=True,
    )
    _run_example(route)


    route = generate_search_pattern_route(
        pattern_type="parallel",
        route_id="search_parallel_0001",
        center_lat_deg=39.4699,
        center_lon_deg=-0.3763,
        altitude_m=400.0,
        desired_speed_kt=110.0,
        leg_length_m=2500.0,
        leg_spacing_m=350.0,
        leg_count=7,
        heading_deg=35.0,
    )
    _run_example(route)


    route = generate_search_pattern_route(
        pattern_type="sector",
        route_id="search_sector_0001",
        center_lat_deg=39.4699,
        center_lon_deg=-0.3763,
        altitude_m=450.0,
        desired_speed_kt=100.0,
        radius_m=1600.0,
        sector_count=3,
        clockwise=False,
    )
    _run_example(route)


    route = generate_search_pattern_route(
        pattern_type="expanding_square",
        route_id="search_square_0001",
        center_lat_deg=39.4699,
        center_lon_deg=-0.3763,
        altitude_m=300.0,
        desired_speed_kt=95.0,
        initial_leg_m=300.0,
        leg_increment_m=250.0,
        leg_count=12,
        heading_deg=0.0,
        clockwise=True,
    )
    _run_example(route)



if __name__ == "__main__":
    run_search_pattern_routes_demo()
