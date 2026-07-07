#!/usr/bin/env python3

# Build simulation JSON/YAML from world settings files.
# Usage: save_simulation_config.py <simulation_name>
# Example: save_simulation_config.py simulation1

import json
import sys
import argparse
from pathlib import Path
from copy import deepcopy
import shutil
from datetime import datetime
from loguru import logger


# get_world_path will get the full path to the world folder
def get_world_path(world_folder) -> Path:
    # Try relative to script location first.
    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent  # scripts -> code -> sw_airsim
    world_path = project_root / "items" / world_folder

    if world_path.exists():
        return world_path

    # Fallback to provided absolute/relative path.
    world_path = Path(world_folder)
    if world_path.exists():
        return world_path

    raise FileNotFoundError(f"World folder not found: {world_folder}")


# load_json_if_exists will load a JSON file if it exists, otherwise returns None
def load_json_if_exists(file_path) -> dict | None:
    file_path = Path(file_path)
    if not file_path.exists():
        return None
    with open(file_path, "r") as f:
        return json.load(f)


# detect_vehicle_from_name will extract the vehicle type from the simulation name.
# The first word (before the first '_') is always the vehicle type.
# Example: "PX4_LondonWorld" -> "PX4", "Veronte_LondonWorld" -> "Veronte"
def detect_vehicle_from_name(simulation_name: str) -> str:
    parts = simulation_name.split("_", 1)
    vehicle = parts[0] if parts else ""
    if vehicle in ("PX4", "Veronte"):
        return vehicle
    return "PX4"  # fallback to PX4 for backward compatibility


# resolve_uav_file will check for the presence of the vehicle JSON in the internal folder first,
# then fallback to the root settings folder
def resolve_uav_file(settings_dir, vehicle_name: str) -> Path:
    filename = f"uav_{vehicle_name.lower()}.json"
    internal_file = settings_dir / "internal" / filename
    if internal_file.exists():
        return internal_file
    return settings_dir / filename


# resolve_uav_px4_file will check for the presence of uav_px4.json in the internal folder first, 
# then fallback to the root settings folder
def resolve_uav_px4_file(settings_dir) -> Path:
    return resolve_uav_file(settings_dir, "PX4")


# merge_vehicle_from_uav_file will merge the vehicle config from the given UAV file data into the simulation data under Vehicles-><vehicle_name>
def merge_vehicle_from_uav_file(simulation_data, uav_data, vehicle_name: str) -> None:
    # If the data is not a dict, does not modify the simulation data
    if not isinstance(uav_data, dict):
        return

    # If vehicle section is not present, does not modify the simulation data
    vehicle_cfg = uav_data.get(vehicle_name)
    if not isinstance(vehicle_cfg, dict):
        return

    # Stores the vehicle config under Vehicles-><vehicle_name> in the simulation data.
    simulation_data.setdefault("Vehicles", {})
    simulation_data["Vehicles"][vehicle_name] = deepcopy(vehicle_cfg)


# merge_px4_from_uav_file kept for backward compatibility
def merge_px4_from_uav_file(simulation_data, uav_px4_data) -> None:
    merge_vehicle_from_uav_file(simulation_data, uav_px4_data, "PX4")


# merge_px4_parameters will merge the Parameters section from the given params data into the simulation data under Vehicles->PX4->Parameters
def merge_px4_parameters(simulation_data, params_data) -> None:
    # If the data is not a dict, does not modify the simulation data
    if not isinstance(params_data, dict):
        return

    # If Parameters section is not present, does not modify the simulation data
    params = params_data.get("Parameters")
    if not isinstance(params, dict):
        return

    # Stores the Parameters under Vehicles->PX4->Parameters in the simulation data.
    simulation_data.setdefault("Vehicles", {})
    simulation_data["Vehicles"].setdefault("PX4", {})
    simulation_data["Vehicles"]["PX4"]["Parameters"] = deepcopy(params)


# merge_cameras_sensors_into_vehicle will merge Cameras and Sensors sections from the given data into the simulation data under 
# Vehicles-><vehicle_name>->Cameras and Vehicles-><vehicle_name>->Sensors
def merge_cameras_sensors_into_vehicle(simulation_data, data, vehicle_name: str) -> None:
    # If the data is not a dict, does not modify the simulation data
    if not isinstance(data, dict):
        return

    simulation_data.setdefault("Vehicles", {})
    simulation_data["Vehicles"].setdefault(vehicle_name, {})

    # If Cameras section is present and is a dict, stores it under Vehicles-><vehicle_name>->Cameras in the simulation data.
    cameras = data.get("Cameras")
    if isinstance(cameras, dict):
        simulation_data["Vehicles"][vehicle_name]["Cameras"] = deepcopy(cameras)

    # If Sensors section is present and is a dict, stores it under Vehicles-><vehicle_name>->Sensors in the simulation data.
    sensors = data.get("Sensors")
    if isinstance(sensors, dict):
        simulation_data["Vehicles"][vehicle_name]["Sensors"] = deepcopy(sensors)


# merge_cameras_sensors_into_px4 kept for backward compatibility
def merge_cameras_sensors_into_px4(simulation_data, data) -> None:
    merge_cameras_sensors_into_vehicle(simulation_data, data, "PX4")


# merge_fleet_into_simulation will store UAV fleet config as top-level uav_0..uav_3 keys
def merge_fleet_into_simulation(simulation_data, fleet_data):
    # Keys to look for
    uav_keys = ("uav_0", "uav_1", "uav_2", "uav_3")
    # If the data is a dict, looks for uav_0..uav_3 keys and stores them at the top level in the simulation data.
    if isinstance(fleet_data, dict):
        filtered_uavs = {k: deepcopy(v) for k, v in fleet_data.items() if k in uav_keys}
        if filtered_uavs:
            for key, value in filtered_uavs.items():
                simulation_data[key] = value


# merge_algorithm_asset_fields will look for dynamic.json, dummy_uavs.json, dynamics_ids.json, static.json in settings/algorithms/assets 
# and merge them into the simulation data if they exist.
def merge_algorithm_asset_fields(simulation_data, settings_dir):
    assets_dir = settings_dir / "algorithms" / "assets"
    field_files = {
        "dynamic": "dynamic.json",          # Contains vehicle trajectories with waypoints [x, y, z, roll_deg, pitch_deg, yaw_deg, time_s]
        "dummy_uavs": "dummy_uavs.json",    # Contains dummy UAV configurations
        "dynamics_ids": "dynamics_ids.json", # Contains dynamic object ID mappings
        "static": "static.json",            # Contains static objects
    }

    # For each field, if the corresponding file exists and is a valid JSON, merge it into the simulation data under the 
    # specified field name.
    for field_name, filename in field_files.items():
        data = load_json_if_exists(assets_dir / filename)
        if data is not None:
            simulation_data[field_name] = deepcopy(data)


# render_json_value will recursively render a value as JSON with custom formatting.
def render_json_value(value, level=0, indent=4) -> str:
    # Computes space for current indentation level
    space = " " * (indent * level)

    # render_waypoints_list will render the waypoints list as a compact JSON array on a single line
    def render_waypoints_list(waypoints: list) -> str:
        if not waypoints:
            return "[]"

        lines = ["["]
        # For each waypoint, serializes it as a JSON string with compact separators and appends it to the lines with a comma
        # if it's not the last waypoint.
        for idx, waypoint in enumerate(waypoints):
            comma = "," if idx < len(waypoints) - 1 else ""
            waypoint_repr = json.dumps(waypoint, ensure_ascii=True, separators=(", ", ": "))
            lines.append(" " * (indent * (level + 1)) + f"{waypoint_repr}{comma}")

        lines.append(space + "]")
        return "\n".join(lines)

    # If the value exists and is a dict
    if isinstance(value, dict):
        # If dict is empty, return {}
        if not value:
            return "{}"

        items = list(value.items())
        lines = ["{"]
        # Iterated over each key-value pair in the dict.
        for idx, (key, item) in enumerate(items):
            # Serializes the key as a JSON string
            key_repr = json.dumps(key, ensure_ascii=True)

            # If the key is "waypoints" and the item is a list, serialize it as one line with compact separators. Otherwise,
            # serialize the item recursively with increased indentation.
            if key == "waypoints" and isinstance(item, list):
                item_repr = render_waypoints_list(item)
            else:
                item_repr = render_json_value(item, level + 1, indent)

            # Adds a comma after the item if it's not the last one in the dict.
            comma = "," if idx < len(items) - 1 else ""
            # Appends the line with the correct format.
            lines.append(" " * (indent * (level + 1)) + f"{key_repr}: {item_repr}{comma}")

        # Closes the dict.
        lines.append(space + "}")
        return "\n".join(lines)

    # If the value exists and is a list
    if isinstance(value, list):
        # If the list is empty, return []
        if not value:
            return "[]"

        # Iterates over each item in the list. Renders each value, adds a comma if it's not the last item and appends it.
        lines = ["["]
        for idx, item in enumerate(value):
            item_repr = render_json_value(item, level + 1, indent)
            comma = "," if idx < len(value) - 1 else ""
            lines.append(" " * (indent * (level + 1)) + f"{item_repr}{comma}")

        # Closes the list.
        lines.append(space + "]")
        return "\n".join(lines)

    # Any of previous: serializes the value directly without processing.
    return json.dumps(value, ensure_ascii=True)


# dumps_simulation_json will serialize the simulation data to a JSON file with custom formatting.
def dumps_simulation_json(data, indent=4) -> str:
    return render_json_value(data, level=0, indent=indent) + "\n"


# build_simulation_data will build the simulation data dictionary by loading and merging data from various settings files in the world folder
def build_simulation_data(world_path, vehicle_name: str = "PX4") -> tuple[dict, dict]:
    settings_dir = world_path
    if not settings_dir.exists():
        raise FileNotFoundError(f"Settings directory not found: {settings_dir}")

    simulation_data = {}
    report = {}

    # 1) Base global config.
    config_file = settings_dir / "config_simulation.json"
    config_data = load_json_if_exists(config_file)
    if isinstance(config_data, dict):
        simulation_data.update(deepcopy(config_data))
        report["config_simulation.json"] = "Loaded"
    else:
        report["config_simulation.json"] = "Missing or invalid"

    # 2) Vehicle base config (PX4 or Veronte depending on simulation name).
    uav_file = resolve_uav_file(settings_dir, vehicle_name)
    uav_data = load_json_if_exists(uav_file)
    if isinstance(uav_data, dict):
        merge_vehicle_from_uav_file(simulation_data, uav_data, vehicle_name)
        report[str(uav_file.relative_to(world_path))] = "Loaded"
    else:
        report[str(uav_file.relative_to(world_path))] = "Missing or invalid"

    # 3) PX4 parameters (only for PX4 vehicle, prefer gnss, fallback ext).
    if vehicle_name == "PX4":
        params_ext_file = settings_dir / "internal" / "params_px4_ext.json"
        params_gnss_file = settings_dir / "internal" / "params_px4_gnss.json"

        params_ext = load_json_if_exists(params_ext_file)
        params_gnss = load_json_if_exists(params_gnss_file)

        if isinstance(params_gnss, dict):
            merge_px4_parameters(simulation_data, params_gnss)
            report["settings/internal/params_px4_gnss.json"] = "Loaded"
        elif isinstance(params_ext, dict):
            merge_px4_parameters(simulation_data, params_ext)
            report["settings/internal/params_px4_ext.json"] = "Loaded"
        else:
            report["settings/internal/params_px4_gnss.json"] = "Missing or invalid"
            report["settings/internal/params_px4_ext.json"] = "Missing or invalid"

    # 4) Cameras/Sensors from sensors.json.
    sensors_file = settings_dir / "sensors.json"
    sensors_data = load_json_if_exists(sensors_file)
    if isinstance(sensors_data, dict):
        merge_cameras_sensors_into_vehicle(simulation_data, sensors_data, vehicle_name)
        report["settings/sensors.json"] = "Loaded"
    else:
        report["settings/sensors.json"] = "Missing or invalid"

    # 5) UAV fleet from fleet.json.
    fleet_file = settings_dir / "fleet.json"
    fleet_data = load_json_if_exists(fleet_file)
    if isinstance(fleet_data, dict):
        merge_fleet_into_simulation(simulation_data, fleet_data)
        report["settings/fleet.json"] = "Loaded (uav_0..uav_3)"
    else:
        report["settings/fleet.json"] = "Missing or invalid"

    # 6) Algorithm assets fields.
    merge_algorithm_asset_fields(simulation_data, settings_dir)
    report["settings/algorithms/assets/*.json"] = "Loaded when present"

    return simulation_data, report


# write_outputs will write the simulation data to a JSON file in the simulations directory and copy the default trajectory 
# YAML
def write_outputs(world_path, simulation_name, simulation_data) -> dict:
    simulations_dir = Path(__file__).parent.parent.parent / "items" / "sim"
    simulations_dir.mkdir(parents=True, exist_ok=True)

    result = {}

    # Write JSON.
    out_json = simulations_dir / f"{simulation_name}.json"
    existed_json = out_json.exists()
    with open(out_json, "w") as f:
        f.write(dumps_simulation_json(simulation_data, indent=4))
    if existed_json:
        result["simulation_json"] = f"Updated ({out_json.name})"
    else:
        result["simulation_json"] = f"Created ({out_json.name})"

    # Copy default trajectory YAML.
    source_yaml = world_path / "settings" / "trajectories" / "default.yaml"
    out_yaml = simulations_dir / f"{simulation_name}.yaml"
    if source_yaml.exists():
        existed_yaml = out_yaml.exists()
        shutil.copy2(source_yaml, out_yaml)
        if existed_yaml:
            result["simulation_yaml"] = f"Updated ({out_yaml.name})"
        else:
            result["simulation_yaml"] = f"Created ({out_yaml.name})"
    else:
        result["simulation_yaml"] = f"Skipped (missing source: {source_yaml})"

    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create simulation JSON/YAML from settings files.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python save_simulation_config.py simulation1\n"
        ),
    )

    parser.add_argument("simulation_name", help="Simulation name without extension (e.g., simulation1)")
    args = parser.parse_args()

    try:
        settings_dir = Path(__file__).parent.parent / "settings"

        vehicle_name = detect_vehicle_from_name(args.simulation_name)
        logger.info(f"Detected vehicle type: {vehicle_name}")

        simulation_data, load_report = build_simulation_data(settings_dir, vehicle_name)
        write_report = write_outputs(settings_dir, args.simulation_name, simulation_data)

        logger.info("\n" + "=" * 60)
        logger.info("Input load report")
        logger.info("=" * 60)
        for key, status in load_report.items():
            logger.info(f"  • {key}: {status}")

        logger.info("\n" + "=" * 60)
        logger.info("Output write report")
        logger.info("=" * 60)
        for key, status in write_report.items():
            logger.info(f"  • {key}: {status}")

        logger.info("\nSave simulation completed")

    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
