#!/usr/bin/env python3

# Apply simulation configuration from a simulation JSON file to the world settings.
# Usage: apply_simulation_config.py <simulation_name>
# Example: apply_simulation_config.py Veronte_LondonWorld

import json
import sys
import argparse
from pathlib import Path
from copy import deepcopy
import shutil
from datetime import datetime
from loguru import logger



# extract_global_config will extract global configuration from the simulation data (config_simulation.json)
def extract_global_config(simulation_data) -> dict:
    # Keys to copy
    global_keys = [
        "SettingsVersion", "LocalHostIp", "ApiServerPort", "LogMessagesVisible",
        "SimMode", "ClockSpeed", "ClockType", "OriginGeopoint", "Recording",
        "SegmentationSettings", "PawnPaths"
    ]
    
    config = {}
    for key in global_keys:
        if key in simulation_data:
            config[key] = deepcopy(simulation_data[key])
    
    return config


# extract_cameras_config will extract cameras configuration from the simulation data (sensors.json)
def extract_cameras_config(simulation_data) -> dict:
    # Keys to copy
    cameras_config = {"Cameras": {}, "Sensors": {}}

    # Copy "Cameras"
    if "Cameras" in simulation_data:
        cameras_config["Cameras"].update(deepcopy(simulation_data["Cameras"]))

    # Copy "Sensors"
    if "Sensors" in simulation_data:
        cameras_config["Sensors"].update(deepcopy(simulation_data["Sensors"]))
    
    # Copy "Cameras" and "Sensors" from defined "Vehicles"
    if "Vehicles" in simulation_data:
        for vehicle_name, vehicle_data in simulation_data["Vehicles"].items():
            if "Cameras" in vehicle_data:
                # Merge cameras from all vehicles
                cameras_config["Cameras"].update(deepcopy(vehicle_data["Cameras"]))

            if "Sensors" in vehicle_data:
                cameras_config["Sensors"].update(deepcopy(vehicle_data["Sensors"]))
    
    return cameras_config


# detect_vehicle_name will detect if the vehicle in the JSON is "PX4" or "Veronte"
def detect_vehicle_name(simulation_data) -> str:
    vehicles = simulation_data.get("Vehicles", {})
    if "PX4" in vehicles:
        return "PX4"
    elif "Veronte" in vehicles:
        return "Veronte"
    return ""


# extract_uav_config will extract vehicle config without Cameras/Sensors and without Parameters
def extract_uav_config(simulation_data, vehicle_name: str) -> dict:
    uav_config = {}

    vehicles = simulation_data.get("Vehicles", {})
    vehicle_data = deepcopy(vehicles.get(vehicle_name, {}))

    if vehicle_data:
        vehicle_data.pop("Cameras", None)
        vehicle_data.pop("Sensors", None)
        vehicle_data.pop("Parameters", None)
        uav_config[vehicle_name] = vehicle_data

    return uav_config


# extract_px4_parameters_config will extract PX4 Parameters (params_px4_ext.json / params_px4_gnss.json)
def extract_px4_parameters_config(simulation_data) -> dict:
    vehicles = simulation_data.get("Vehicles", {})
    px4_vehicle = vehicles.get("PX4", {})
    parameters = deepcopy(px4_vehicle.get("Parameters", {}))

    if parameters:
        return {"Parameters": parameters}
    return {}


# extract_fleet_uavs_config will extract UAV fleet data for fleet.json
def extract_fleet_uavs_config(simulation_data) -> dict:
    # Keys to copy
    uav_keys = ("uav_0", "uav_1", "uav_2")
    source = {k: simulation_data[k] for k in uav_keys if k in simulation_data}

    if not source:
        return None

    return {k: deepcopy(v) for k, v in source.items() if k in uav_keys}


# extract_algorithm_asset_config will extract algorithm asset field from simulation data
# Preserves complete structure including waypoints with orientation data [x, y, z, roll_deg, pitch_deg, yaw_deg, time_s]
def extract_algorithm_asset_config(simulation_data, field_name):
    if field_name in simulation_data:
        return deepcopy(simulation_data[field_name])
    return None

def ensure_file_path(path: Path) -> None:
    """If path exists as a directory, remove it. Then ensure parent exists."""
    if path.is_dir():
        shutil.rmtree(path)
    path.parent.mkdir(parents=True, exist_ok=True)

# apply_config will apply the extracted configuration to all relevant files
def apply_config(settings_dir, simulation_name, simulation_data) -> dict:
    # Search for settings directory
    settings_dir.mkdir(parents=True, exist_ok=True)
    
    results = {}
    
    # 1. Update config_simulation.json (global config)
    config_file = settings_dir / "config_simulation.json"
    ensure_file_path(config_file)
    try:
        global_config = extract_global_config(simulation_data)
        with open(config_file, 'w') as f:
            json.dump(global_config, f, indent=4)
        results["config_simulation.json"] = "Updated"
    except Exception as e:
        results["config_simulation.json"] = f"Error: {e}"
    
    # 2. Update sensors.json (cameras config)
    sensors_file = settings_dir / "sensors.json"
    ensure_file_path(sensors_file)
    try:
        cameras_config = extract_cameras_config(simulation_data)
        with open(sensors_file, 'w') as f:
            json.dump(cameras_config, f, indent=4)
        results["sensors.json"] = "Updated"
    except Exception as e:
        results["sensors.json"] = f"Error: {e}"
    
    # Ensure internal directory exists
    internal_dir = settings_dir / "internal"
    internal_dir.mkdir(parents=True, exist_ok=True)
    
    # 3. Detect vehicle name and create/update the appropriate UAV config file
    vehicle_name = detect_vehicle_name(simulation_data)
    if vehicle_name == "PX4":
        uav_file = internal_dir / "uav_px4.json"
        uav_result_key = "uav_px4.json"
    elif vehicle_name == "Veronte":
        uav_file = internal_dir / "uav_veronte.json"
        uav_result_key = "uav_veronte.json"
    else:
        uav_file = None
        uav_result_key = None

    if uav_file:
        ensure_file_path(uav_file)
        try:
            uav_config = extract_uav_config(simulation_data, vehicle_name)
            with open(uav_file, 'w') as f:
                json.dump(uav_config, f, indent=4)
            results[uav_result_key] = "Updated"
        except Exception as e:
            results[uav_result_key] = f"Error: {e}"
    
    # 4. Create/update fleet.json with UAV fleet data
    fleet_file = settings_dir / "fleet.json"
    ensure_file_path(fleet_file)
    try:
        fleet_config = extract_fleet_uavs_config(simulation_data)
        if fleet_config is not None:
            with open(fleet_file, 'w') as f:
                json.dump(fleet_config, f, indent=4)
            results["fleet.json"] = "Updated"
    except Exception as e:
        results["fleet.json"] = f"Error: {e}"

    # 5. Create/update PX4 parameters files (only when vehicle is PX4)
    if vehicle_name == "PX4":
        params_ext_file = internal_dir / "params_px4_ext.json"
        params_gnss_file = internal_dir / "params_px4_gnss.json"
        ensure_file_path(params_ext_file)
        ensure_file_path(params_gnss_file)
        try:
            params_config = extract_px4_parameters_config(simulation_data)
            if params_config:
                for params_file, result_key in [
                    (params_ext_file, "params_px4_ext.json"),
                    (params_gnss_file, "params_px4_gnss.json"),
                ]:
                    with open(params_file, 'w') as f:
                        json.dump(params_config, f, indent=4)
                    results[result_key] = "Updated"
        except Exception as e:
            results["params_px4_ext.json"] = f"Error: {e}"
            results["params_px4_gnss.json"] = f"Error: {e}"

    # 6. Create/update algorithms/assets JSONs from simulation_data fields
    asset_fields = ["dynamic", "dummy_uavs", "dynamics_ids", "static"]
    assets_dir = settings_dir / "algorithms" / "assets"
    for field_name in asset_fields:
        try:
            field_data = extract_algorithm_asset_config(simulation_data, field_name)
            if field_data is None:
                continue

            target_file = assets_dir / f"{field_name}.json"
            ensure_file_path(target_file)
            with open(target_file, 'w') as f:
                json.dump(field_data, f, indent=4)

            results[f"{field_name}.json"] = "Updated"
        except Exception as e:
            results[f"{field_name}.json"] = f"Error: {e}"

    # 7. Copy simulation YAML to trajectories/default.yaml
    sim_dir = Path(__file__).parent.parent.parent / "items" / "sim"
    source_yaml = sim_dir / f"{simulation_name}.yaml"
    target_yaml = settings_dir / "trajectories" / "default.yaml"
    try:
        if source_yaml.exists():
            ensure_file_path(target_yaml)
            shutil.copy2(source_yaml, target_yaml)
            results["trajectories/default.yaml"] = "Updated"
        else:
            results["trajectories/default.yaml"] = f"Skipped (missing source: {source_yaml.name})"
    except Exception as e:
        results["trajectories/default.yaml"] = f"Error: {e}"
    
    return results


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Apply simulation configuration from a simulation JSON file to world settings.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            python apply_simulation_config.py simulation1
            python apply_simulation_config.py /full/path/to simulation1
                    """
                )
    
    # Two arguments: world_folder and simulation_name
    parser.add_argument("simulation_name", help="Name of the simulation JSON file without extension (e.g., simulation1)")
    
    args = parser.parse_args()
    
    try:
        # Get simulation file path
        settings_dir = Path(__file__).parent.parent / "settings"
        sim_dir = Path(__file__).parent.parent.parent / "items" / "sim"
        sim_file = sim_dir / f"{args.simulation_name}.json"
        if not sim_file.exists():
            raise FileNotFoundError(f"Simulation file not found: {sim_file}")
        logger.info(f"Simulation file: {sim_file}")
        
        # Load simulation data
        with open(sim_file, 'r') as f:
            simulation_data = json.load(f)
        logger.info(f"Loaded simulation configuration")
        
        # Apply configuration
        results = apply_config(settings_dir, args.simulation_name, simulation_data)
        
        # Print results
        logger.info("\n" + "="*60)
        logger.info("Configuration applied to:")
        logger.info("="*60)
        for filename, status in results.items():
            logger.info(f"  • {filename}: {status}")
        
        logger.info("\nConfiguration successfully applied!")
        logger.info(f"Settings directory: /settings/")
        
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
