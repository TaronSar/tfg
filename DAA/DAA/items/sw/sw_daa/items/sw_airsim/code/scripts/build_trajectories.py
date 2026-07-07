#!/usr/bin/env python3
"""
Read track_1 from an encounter HDF5 file, convert east/north/up from feet to
meters and copy it into dynamic.militarHelicopter3.waypoints of a simulation
JSON file.
"""
import sys
import os
import argparse
import json
import math
from typing import List, Optional

import h5py
import numpy as np

from airsim.utils import to_quaternion
from loguru import logger


FEET_TO_METERS = 0.3048
KNOTS_TO_METERS_PER_SECOND = 0.5144444444444445
RADIANS_TO_DEGREES = 180.0 / math.pi
DEFAULT_TRACK_ID = "track_1"
DEFAULT_YAML_TRACK_ID = "track_0"
DEFAULT_VEHICLE_NAME = "militarHelicopter3"
DEFAULT_SIMULATION_FILE = (
    "../../items/"
    "../../items/sim/simulation_trajectories_example.json"
)

# TrajectoryUpdater will read one encounter track from HDF5 and write it into a simulation file.
# Reads passed track from HD5 file, converts east/north/up from feet to meters, copies them into dynamic - object - waypoints of
# a simulation JSON file. Also copies the orientation phi_rad, psi_rad, theta_rad (roll, yaw, pitch) converting from radians to
# degrees and the actual_speed
class TrajectoryUpdater:

    # __init__ initializes the TrajectoryUpdater with the path to the HDF5 file containing encounters.
    def __init__(self, h5_file: str):
        self.h5_file = h5_file

    # load_track_data reads the specified track from the HDF5 file and returns the enconter_id used, a list of waypoints with east,
    # north, up converted from feet to meters and orientation angles converted from radians to degrees, and the actual speed in 
    # meters per second.
    def load_track_data(self, encounter_id: Optional[str] = None, track_id: str = DEFAULT_TRACK_ID,) -> tuple[str, List[List[float]], float]:
        return self._load_track_data_internal(encounter_id, track_id, convert_to_degrees=True)

    # load_track_data_radians reads the specified track from the HDF5 file and returns angles in radians (no conversion).
    # This is more efficient when we need to keep angles in radians.
    def load_track_data_radians(self, encounter_id: Optional[str] = None, track_id: str = DEFAULT_TRACK_ID,) -> tuple[str, List[List[float]], float]:
        return self._load_track_data_internal(encounter_id, track_id, convert_to_degrees=False)

    # _load_track_data_internal is the internal implementation that can optionally convert angles to degrees.
    def _load_track_data_internal(self, encounter_id: Optional[str] = None, track_id: str = DEFAULT_TRACK_ID, convert_to_degrees: bool = True) -> tuple[str, List[List[float]], float]:
        # Opens the file
        with h5py.File(self.h5_file, "r") as h5_file:
            # Reads the encounters group. If it doesn't exist, raises an error.
            encounters_group = h5_file.get("encounters")
            if encounters_group is None:
                raise ValueError(f"No 'encounters' group found in {self.h5_file}")

            # Reads the encounter keys. If there are no encounters, raises an error.
            encounter_keys = sorted(encounters_group.keys())
            if not encounter_keys:
                raise ValueError(f"No encounters found in {self.h5_file}")

            # Selects the encounter to use. If encounter_id is not provided, uses the first one. If it doesn't exist, raises an error.
            selected_encounter_id = encounter_id or encounter_keys[0]
            if selected_encounter_id not in encounters_group:
                raise ValueError(f"Encounter '{selected_encounter_id}' not found")

            # Reads the results group of the selected encounter. If it doesn't exist, raises an error.
            encounter_group = encounters_group[selected_encounter_id]
            results_group = encounter_group.get("results")
            if results_group is None:
                raise ValueError(f"Encounter '{selected_encounter_id}' has no 'results' group")

            # Selects the track in the results group. If it doesn't exist, raises an error.
            if track_id not in results_group:
                raise ValueError(
                    f"Track '{track_id}' not found in encounter '{selected_encounter_id}'"
                )

            # Obtains track and from it: east, north, up in feet; phi, psi, theta in radians; time in seconds; and actual speed in knots.
            track_group = results_group[track_id]
            east = track_group["east_ft"][:]
            north = track_group["north_ft"][:]
            up = track_group["up_ft"][:]
            phi_rad = track_group["phi_rad"][:]      # roll in radians
            psi_rad = track_group["psi_rad"][:]      # heading/yaw in radians
            theta_rad = track_group["theta_rad"][:]  # pitch in radians
            time_s = track_group["time"][:]
            actual_speed_knots = float(track_group["actual_speed"][()])

            # Checks that all arrays have the same length. If not, raises an error.
            if not (len(east) == len(north) == len(up) == len(phi_rad) == len(psi_rad) == len(theta_rad) == len(time_s)):
                raise ValueError("east_ft, north_ft, up_ft, phi_rad, psi_rad, theta_rad, time do not have the same length")

            # Generates waypoints list with east, north, up converted from feet to meters with 6 decimal places.
            # Orientation angles can be kept in radians or converted to degrees based on convert_to_degrees parameter.
            if convert_to_degrees:
                # Convert angles from radians to degrees (for JSON)
                waypoints = [
                    [
                        round(float(east_value) * FEET_TO_METERS, 6),
                        round(float(north_value) * FEET_TO_METERS, 6),
                        round(float(up_value) * FEET_TO_METERS, 6),
                        round(float(phi_value) * RADIANS_TO_DEGREES, 6),    # roll in degrees
                        round(float(theta_value) * RADIANS_TO_DEGREES, 6),  # pitch in degrees
                        round(float(psi_value) * RADIANS_TO_DEGREES, 6),    # yaw in degrees
                        round(float(t), 6),                                  # time in seconds
                    ]
                    for east_value, north_value, up_value, phi_value, theta_value, psi_value, t in zip(east, north, up, phi_rad, theta_rad, psi_rad, time_s)
                ]
            else:
                # Keep angles in radians (for YAML)
                waypoints = [
                    [
                        round(float(east_value) * FEET_TO_METERS, 6),
                        round(float(north_value) * FEET_TO_METERS, 6),
                        round(float(up_value) * FEET_TO_METERS, 6),
                        round(float(phi_value), 6),     # roll in radians
                        round(float(theta_value), 6),   # pitch in radians
                        round(float(psi_value), 6),     # yaw in radians
                        round(float(t), 6),              # time in seconds
                    ]
                    for east_value, north_value, up_value, phi_value, theta_value, psi_value, t in zip(east, north, up, phi_rad, theta_rad, psi_rad, time_s)
                ]
            
            # Converts speed from knots to meters per second with 6 decimal places.
            actual_speed_meters_per_second = round(
                actual_speed_knots * KNOTS_TO_METERS_PER_SECOND,
                6,
            )

            # Returns the selected encounter id, the waypoints list and the actual speed
            return selected_encounter_id, waypoints, actual_speed_meters_per_second

    # update_simulation_file reads the specified track from the file, converts the waypoints and speed, and updates the specified
    # simulation JSON file
    def update_simulation_file(self, simulation_file: str, encounter_id: Optional[str] = None, track_id: str = DEFAULT_TRACK_ID, vehicle_name: str = DEFAULT_VEHICLE_NAME, time_offset: Optional[float] = None, scale_xy: float = 1.0) -> tuple[int, float]:
        # Loads track data
        _, waypoints, actual_speed_meters_per_second = self.load_track_data(encounter_id=encounter_id, track_id=track_id)

        # Opens the simulation file, reads the JSON data, updates the waypoints and speed for the specified vehicle,
        # and writes the updated JSON back to the file.
        with open(simulation_file, "r") as file_handle:
            simulation_data = json.load(file_handle)

        # Checks that the simulation data contains the expected dynamic structure. If not, raises an error.
        dynamic_data = simulation_data.get("dynamic")
        if not isinstance(dynamic_data, dict):
            raise ValueError(f"File '{simulation_file}' does not contain a top-level 'dynamic' object")

        # Checks that the specified vehicle exists in the dynamic structure. If not, raises an error.
        vehicle_data = dynamic_data.get(vehicle_name)
        if not isinstance(vehicle_data, dict):
            raise ValueError(f"Vehicle '{vehicle_name}' not found inside 'dynamic'")

        # Apply scale factor to x, y coordinates
        scaled_waypoints = [
            [
                round(waypoint[0] / scale_xy, 6),  # east (x) scaled
                round(waypoint[1] / scale_xy, 6),  # north (y) scaled
                waypoint[2],  # up (z) unchanged
                waypoint[3],  # roll_deg unchanged
                waypoint[4],  # pitch_deg unchanged
                waypoint[5],  # yaw_deg unchanged
                waypoint[6],  # time (s) unchanged
            ]
            for waypoint in waypoints
        ]

        # Writes waypoints and velocity into the vehicle data.
        vehicle_data["waypoints"] = scaled_waypoints
        vehicle_data["velocity"] = actual_speed_meters_per_second

        # Writes the updated simulation data back to the file with indentation for readability and a newline at the end.
        with open(simulation_file, "w") as file_handle:
            json.dump(simulation_data, file_handle, indent=4)
            file_handle.write("\n")

        # Returns the number of waypoints written and the actual speed in meters per second
        return len(waypoints), actual_speed_meters_per_second

    # update_trajectory_yaml_from_track updates the trajectory YAML with transformed waypoints from a track.
    # It keeps wp_0 unchanged and starts writing loaded points from wp_1.
    def update_trajectory_yaml_from_track(self, yaml_file: str, encounter_id: Optional[str] = None, track_id: str = DEFAULT_YAML_TRACK_ID, scale_xy: float = 1.0,) -> int:
        # Load track data in radians
        _, waypoints, _ = self.load_track_data_radians(encounter_id=encounter_id, track_id=track_id)

        # MIN scale is 1
        if scale_xy == 0:
            raise ValueError("scale_xy cannot be 0")

        # Reads YAML - preserves wp_0
        frame_id_line = "frame_id: uav_0/odom"
        wp0_line = None
        if os.path.exists(yaml_file):
            with open(yaml_file, "r") as file_handle:
                for raw_line in file_handle:
                    line = raw_line.rstrip("\n")
                    stripped = line.strip()
                    if stripped.startswith("frame_id:"):
                        frame_id_line = stripped
                    elif stripped.startswith("wp_0:"):
                        wp0_line = stripped

        if wp0_line is None:
            raise ValueError(f"YAML file '{yaml_file}' does not contain 'wp_0' to preserve")

        # Writes waypoints
        output_lines = [frame_id_line, wp0_line]
        for idx, waypoint in enumerate(waypoints):
            x = round(waypoint[0] / scale_xy, 6)
            y = round(waypoint[1] / scale_xy, 6)
            z = round(waypoint[2], 6)
            t = waypoint[6]

            # Angles are already in radians from load_track_data_radians, use them directly
            qx, qy, qz, qw = self.euler_radians_to_quaternion(roll_rad=waypoint[3], pitch_rad=waypoint[4], yaw_rad=waypoint[5])

            wp_index = idx + 1
            output_lines.append(
                f"wp_{wp_index}: [{x}, {y}, {z}, {qx}, {qy}, {qz}, {qw}, {t}]"
            )

        # Writes the updated trajectory data back to the YAML file with a newline at the end.
        with open(yaml_file, "w") as file_handle:
            file_handle.write("\n".join(output_lines) + "\n")

        return len(waypoints)


    # euler_radians_to_quaternion converts roll, pitch, yaw in radians to a quaternion tuple (qx, qy, qz, qw) rounded to 12 decimal places.
    # TODO: Validate yaw without pi/2 adjustment. Or if it is necessary to add it.
    @staticmethod
    def euler_radians_to_quaternion(roll_rad: float, pitch_rad: float, yaw_rad: float) -> tuple[float, float, float, float]:
        # Add π/2 to yaw so the UAV orientation in AirSim matches the dynamic objects coordinate frame.
        quat = to_quaternion(roll=roll_rad, pitch=pitch_rad, yaw=yaw_rad + (math.pi / 2))
        return (round(quat.x_val, 12), round(quat.y_val, 12), round(quat.z_val, 12), round(quat.w_val, 12))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Copy track from an HDF5 encounter into dynamic waypoints of a simulation JSON file,"
            "converting feet to meters and including position and orientation data."
        )
    )
    parser.add_argument("h5_file", help="Path to the HDF5 file with encounters")
    parser.add_argument(
        "--simulation-file",
        default=DEFAULT_SIMULATION_FILE,
        help="Simulation JSON to update",
    )
    parser.add_argument(
        "--encounter-id",
        help="Encounter id to use. Defaults to the first available encounter.",
    )
    parser.add_argument(
        "--track-id",
        default=DEFAULT_TRACK_ID,
        help="Track id to copy. Defaults to track_1.",
    )
    parser.add_argument(
        "--vehicle-name",
        default=DEFAULT_VEHICLE_NAME,
        help="Dynamic vehicle name to overwrite. Defaults to militarHelicopter3.",
    )
    parser.add_argument(
        "--time-offset",
        type=float,
        help="Optional wait time in seconds before the dynamic asset starts moving.",
    )
    parser.add_argument(
        "--scale-xy",
        type=float,
        default=1.0,
        help="Scale factor for X, Y coordinates. Factor of 2 divides coordinates by 2 (brings waypoints closer). Default is 1.0 (no scaling).",
    )
    parser.add_argument(
        "--yaml-track-id",
        default=DEFAULT_YAML_TRACK_ID,
        help="Track id to copy into trajectory YAML. Defaults to track_0.",
    )

    args = parser.parse_args()

    updater = TrajectoryUpdater(args.h5_file)
    waypoint_count, actual_speed_meters_per_second = updater.update_simulation_file(
        simulation_file=args.simulation_file,
        encounter_id=args.encounter_id,
        track_id=args.track_id,
        vehicle_name=args.vehicle_name,
        time_offset=args.time_offset,
        scale_xy=args.scale_xy,
    )

    trajectory_yaml = os.path.splitext(args.simulation_file)[0] + ".yaml"

    yaml_waypoint_count = updater.update_trajectory_yaml_from_track(
        yaml_file=trajectory_yaml,
        encounter_id=args.encounter_id,
        track_id=args.yaml_track_id,
        scale_xy=args.scale_xy,
    )

    logger.info(f"Updated '{args.vehicle_name}' in {args.simulation_file}")
    logger.info(f"Waypoints written: {waypoint_count}")
    logger.info(f"Velocity written: {actual_speed_meters_per_second} m/s")
    logger.info(f"Updated trajectory YAML: {trajectory_yaml}")
    logger.info(f"YAML waypoints written from {args.yaml_track_id} as wp_1..wp_{yaml_waypoint_count} (wp_0 preserved)")
    logger.info("JSON waypoint format: [east_m, north_m, up_m, roll_deg, pitch_deg, yaw_deg, time_s]")
    logger.info("YAML waypoint format: [x_m, y_m, z_m, qx, qy, qz, qw, time_s] (quaternions in AirSim coordinate frame)")
    if args.time_offset is not None:
        logger.info(f"Time offset set to: {args.time_offset} s")
    if args.scale_xy != 1.0:
        logger.info(f"X, Y coordinates scaled by factor: {args.scale_xy} (divided by {args.scale_xy})")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        logger.error(f"{error}")
        sys.exit(1)
