#!/usr/bin/env python3
"""
verify_sensors.py - Verification of AirSim sensors for Veronte vehicle.

Checks that all configured sensors are accessible:
  1. Via AirSim Python API (getImuData, getGpsData, etc.)
  2. Via ROS topics (requires running inside the AirSim container with ROS active)

Displays raw data from each sensor and measures the actual sampling frequency.

Usage:
  # API-only verification (from host or container):
  python verify_sensors.py --api-only

  # Full API + ROS verification (from container with ROS):
  python verify_sensors.py

  # Change frequency measurement duration (default 120s):
  python verify_sensors.py --duration 60
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple, Type
from loguru import logger

import airsim


def _bootstrap_bridge_imports() -> None:
    """Ensure the local veronte_sil scripts root is importable as `bridge.*`."""
    this_file = Path(__file__).resolve()
    scripts_root = None

    for parent in this_file.parents:
        candidate = (
            parent /"sw"/"sw_daa"/"items"/"_sw_perception"/"items"/"sw_gnssdenied"/"items"/"sw_rosws"/"src"/"veronte_sil"/"scripts"
        )
        if candidate.is_dir():
            scripts_root = candidate
            break

    if scripts_root is None:
        raise RuntimeError(
            "Could not locate veronte_sil/scripts directory required for bridge imports"
        )

    scripts_root_str = str(scripts_root)
    if scripts_root_str not in sys.path:
        sys.path.insert(0, scripts_root_str)


_bootstrap_bridge_imports()

from bridge.gps_airsim import GPSAirSim
from bridge.imu_airsim import IMUAirSim
from bridge.barometer_airsim import BarometerAirSim
from bridge.magnetometer_airsim import MagnetometerAirSim
from bridge.lidar_airsim import LidarAirSim
from bridge.sensor_result import SensorResult

DEFAULT_VEHICLE_NAME = "Veronte"
SENSORS_CONFIG_PATH = Path(__file__).resolve().parents[1] / "settings" / "sensors.json"

SENSOR_CATEGORY_TO_GROUP = {
    "barometer": "barometer",
    "imu": "imu",
    "gps": "gnss",
    "magnetometer": "magnetometer",
    "lidar": "lidar",
}

# API frequency sampling loop pacing.
API_POLL_SLEEP_S = 0.001

class VerifySensors:
    """AirSim sensor verification tool for Veronte vehicle."""

    # VerifySensors::__init__ will load sensor names from the JSON configuration and categorize them by type.
    # \param[in] vehicle_name AirSim vehicle name to verify (default: "Veronte") [str]
    def __init__(self, vehicle_name: str = DEFAULT_VEHICLE_NAME):
        self.vehicle_name = vehicle_name
        self.barometers: List[str] = []
        self.imus: List[str] = []
        self.gps_sensors: List[str] = []
        self.magnetometers: List[str] = []
        self.lidars: List[str] = []
        
        # Load sensor names from configuration
        self._configure_sensor_lists()

    # VerifySensors::_configure_sensor_lists will read the sensor names from the JSON configuration file and
    # populate the corresponding lists for each one.
    def _configure_sensor_lists(self):
        grouped_sensors = self._load_sensor_names()
        self.barometers = grouped_sensors["barometer"]
        self.imus = grouped_sensors["imu"]
        self.gps_sensors = grouped_sensors["gnss"]
        self.magnetometers = grouped_sensors["magnetometer"]
        self.lidars = grouped_sensors["lidar"]

    # VerifySensors::_load_sensor_names will read the sensors.json file, parse the sensor names and group them by category.
    # \return Dictionary mapping sensor groups to lists of sensor names [Dict[str, List[str]]]
    def _load_sensor_names(self) -> Dict[str, List[str]]:
        with SENSORS_CONFIG_PATH.open(encoding="utf-8") as sensor_file:
            config = json.load(sensor_file)

        sensors = config.get("Sensors")
        if not isinstance(sensors, dict):
            raise ValueError(
                f"No dictionary found in {SENSORS_CONFIG_PATH}['Sensors']"
            )

        grouped_sensors = {group: [] for group in SENSOR_CATEGORY_TO_GROUP.values()}
        for sensor_name in sensors:
            category = sensor_name.split("_", 1)[0].strip().lower()
            group = SENSOR_CATEGORY_TO_GROUP.get(category)
            if group is not None:
                grouped_sensors[group].append(sensor_name)

        return grouped_sensors

    # VerifySensors::_build_sensor_verification_configs will create a consolidated list of sensor verification configurations.
    # This centralizes the sensor class mappings to avoid duplication.
    # \return List of tuples (group_name, sensor_class, sensor_names) for API verification [List[Tuple[str, Type, List[str]]]]
    def _build_sensor_verification_configs(self) -> List[Tuple[str, Type, List[str]]]:
        return [
            ("IMU", IMUAirSim, self.imus),
            ("GPS", GPSAirSim, self.gps_sensors),
            ("Barometer", BarometerAirSim, self.barometers),
            ("Magnetometer", MagnetometerAirSim, self.magnetometers),
            ("LiDAR", LidarAirSim, self.lidars)
        ]

    # VerifySensors::_get_sensor_group_configs will return the sensor group configurations, including the sensor names,
    # ROS topic categories, API labels, message type and API call lambdas for each one.
    # \return Dictionary mapping sensor groups to their configurations [Dict[str, Dict[str, object]]]
    def _get_sensor_group_configs(self) -> Dict[str, Dict[str, object]]:
        return {
            "barometer": {
                "sensor_names": self.barometers,
                "topic_category": "barometer",
                "api_label": "Barometer",
                "msg_type": "airsim_ros_pkgs/Barometer",
                "api_call": lambda client, sensor_name: client.getBarometerData(sensor_name, self.vehicle_name),
            },
            "imu": {
                "sensor_names": self.imus,
                "topic_category": "imu",
                "api_label": "IMU",
                "msg_type": "sensor_msgs/Imu",
                "api_call": lambda client, sensor_name: client.getImuData(sensor_name, self.vehicle_name),
            },
            "gnss": {
                "sensor_names": self.gps_sensors,
                "topic_category": "gnss",
                "api_label": "GPS",
                "msg_type": "sensor_msgs/NavSatFix",
                "api_call": lambda client, sensor_name: client.getGpsData(sensor_name, self.vehicle_name),
            },
            "magnetometer": {
                "sensor_names": self.magnetometers,
                "topic_category": "magnetometer",
                "api_label": "Magnetometer",
                "msg_type": "sensor_msgs/MagneticField",
                "api_call": lambda client, sensor_name: client.getMagnetometerData(sensor_name, self.vehicle_name),
            },
            "lidar": {
                "sensor_names": self.lidars,
                "topic_category": "lidar",
                "api_label": "LiDAR",
                "msg_type": "sensor_msgs/PointCloud2",
                "api_call": lambda client, sensor_name: client.getLidarData(sensor_name, self.vehicle_name),
            },
        }


    # VerifySensors::_build_representative_sensor_registry will create a registry of representative sensors for frequency
    # measurement.
    # \return Dictionary mapping sensor names to their API call information for frequency measurement [Dict[str, Dict[str, object]]]
    def _build_representative_sensor_registry(self) -> Dict[str, Dict[str, object]]:
        representative_sensors = {}

        for config in self._get_sensor_group_configs().values():
            sensor_names = config["sensor_names"]
            if not sensor_names:
                continue

            sensor_name = sensor_names[0]
            representative_sensors[sensor_name] = {
                "sensor_name": sensor_name,
                "topic": f"/airsim_node/{self.vehicle_name}/{config['topic_category']}/{sensor_name}",
                "api_call": config["api_call"],
                "api_label": config["api_label"],
                "msg_type": config["msg_type"],
            }

        return representative_sensors

    # VerifySensors::_build_ros_topics will create the ROS topic paths for all sensors.
    # \return Dictionary mapping sensor groups to lists of their expected ROS topic paths [Dict[str, List[str]]]
    def _build_ros_topics(self) -> Dict[str, List[str]]:
        ros_topics = {
            key: [f"/airsim_node/{self.vehicle_name}/{cfg['topic_category']}/{name}" for name in cfg["sensor_names"]]
            for key, cfg in self._get_sensor_group_configs().items()
        }
        ros_topics["other"] = [
            f"/airsim_node/{self.vehicle_name}/global_gnss",
            f"/airsim_node/{self.vehicle_name}/environment",
            f"/airsim_node/{self.vehicle_name}/ground_truth/pose",
            f"/airsim_node/{self.vehicle_name}/odom",
        ]

        return ros_topics

    # VerifySensors::_separator will generate a formatted separator line for better readability in logs.
    @staticmethod
    def _separator(title: str) -> str:
        return f"\n{'='*70}\n  {title}\n{'='*70}"
        

    # VerifySensors::_measure_api_frequency will measure the polling frequency of the AirSim API for each representative 
    # sensor and estimate the actual sensor update frequency based on unique timestamps.
    # \param[in] client AirSim MultirotorClient instance to use for API calls [airsim.MultirotorClient]
    # \param[in] duration Duration in seconds to perform the measurement for each sensor [float]
    # \return Dictionary mapping sensor names to their measured API poll rate and sensor update frequency [Dict[str, Dict[str, float]]]
    def _measure_api_frequency(self, client: airsim.MultirotorClient, duration: float) -> Dict[str, Dict[str, float]]:
        frequencies = {}
        duration_ns = int(duration * 1e9)

        representative_sensors = self._build_representative_sensor_registry()

        # Initialize timestamp and count collection for all sensors
        sensor_data_collection = {
            sensor_name: {"timestamps": [], "count": 0}
            for sensor_name in representative_sensors.keys()
        }

        # Measure all sensors in parallel for the specified duration
        start_ns = time.perf_counter_ns()
        while (time.perf_counter_ns() - start_ns) < duration_ns:
            for sensor_name, sensor_data in representative_sensors.items():
                call_fn = sensor_data["api_call"]
                try:
                    data = call_fn(client, sensor_name)
                    ts = getattr(data, "time_stamp", None)
                    if ts is None and hasattr(data, "gnss"):
                        ts = data.gnss.time_utc
                    if ts is not None:
                        sensor_data_collection[sensor_name]["timestamps"].append(ts)

                    sensor_data_collection[sensor_name]["count"] += 1
                except Exception as e:
                    logger.warning(f"Error reading sensor {sensor_name} via API: {e}")
            time.sleep(API_POLL_SLEEP_S)

        elapsed = (time.perf_counter_ns() - start_ns) / 1e9

        # Calculate frequencies for each sensor
        for sensor_name, sensor_data in representative_sensors.items():
            name = f"{sensor_data['api_label']} ({sensor_name})"
            count = sensor_data_collection[sensor_name]["count"]
            timestamps = set(sensor_data_collection[sensor_name]["timestamps"])
            api_rate = count / elapsed if elapsed > 0 else 0

            # Use wall-clock elapsed (same as ROS) so both modes are directly comparable.
            # Deduplicate by sensor timestamp to avoid counting repeated API reads of the same sample.
            unique_ts = sorted(timestamps)
            n_unique = len(unique_ts)
            if n_unique > 1 and elapsed > 0:
                sensor_freq = (n_unique - 1) / elapsed
                unique_samples_per_sec = n_unique / elapsed
            else:
                sensor_freq = 0
                unique_samples_per_sec = 0

            frequencies[name] = {
                "api_poll_rate_hz": api_rate,
                "sensor_update_hz": sensor_freq,
                "unique_samples_per_sec": unique_samples_per_sec,
            }

        return frequencies

    # VerifySensors::_report_sensor_group_results will log the verification results for a group of sensors and 
    # count how many were accessible vs inaccessible.
    # \param[in] group_name Name of the sensor group (e.g. "IMU", "GPS") [str]
    # \param[in] results List of SensorResult objects containing the verification results for each sensor in the group [List[SensorResult]]
    # \return Dictionary containing the count of accessible and inaccessible sensors in the group [Dict[str, int]]
    @staticmethod
    def _report_sensor_group_results(group_name: str, results: List[SensorResult]) -> Dict[str, int]:
        logger.info(f"\n--- {group_name} ---")
        
        # Validate and handle empty results
        if not results:
            logger.warning(f"No sensors to verify in {group_name} group")
            return {"ok": 0, "fail": 0}
        
        group_ok = 0
        group_fail = 0

        for result in results:
            status = "OK" if result.accessible else "FAIL"
            logger.info(f"  [{status}] {result.name}")
            if result.accessible:
                logger.info(result.data_summary)
                group_ok += 1
            else:
                logger.info(f"    {result.error}")
                group_fail += 1

        return {"ok": group_ok, "fail": group_fail}

    # VerifySensors::_verify_topics will check the presence of expected ROS topics for all sensors and report 
    # which ones are found or missing.
    # \param[in] ros_topics Dictionary mapping sensor groups to lists of their expected ROS topic paths [Dict[str, List[str]]]
    # \param[in] rostopic module to use for checking topic types (imported inside run_ros_verification) [module]
    # \return Dictionary containing the count of found and missing topics, and the set of discovered message types [Dict[str, object]]
    def _verify_topics(self, ros_topics: Dict[str, List[str]], rostopic) -> Dict[str, any]:
        logger.info("\n--- Verification of published topics ---\n")

        topics_found = 0
        topics_missing = 0
        discovered_types = set()

        for category, topics in ros_topics.items():
            logger.info(f"  [{category.upper()}]")
            for topic in topics:
                try:
                    topic_type, _, _ = rostopic.get_topic_type(topic)
                    exists = topic_type is not None
                except Exception:
                    exists = False

                status = "OK" if exists else "MISSING"
                type_str = f" ({topic_type})" if exists else ""
                logger.info(f"    [{status}] {topic}{type_str}")
                if exists:
                    topics_found += 1
                    if topic_type:
                        discovered_types.add(topic_type)
                else:
                    topics_missing += 1

        return {
            "topics_found": topics_found,
            "topics_missing": topics_missing,
            "discovered_types": discovered_types,
        }

    # VerifySensors::_report_discovered_message_types will log the ROS message types that were discovered during topic 
    # verification, along with their field descriptions if available.
    # \param[in] discovered_types Set of discovered ROS message types [Set[str]]
    @staticmethod
    def _report_discovered_message_types(discovered_types: Set[str]) -> None:
        if not discovered_types:
            return

        logger.info("\n--- Description of message types ---\n")
        for msg_type in sorted(discovered_types):
            logger.info(f"  [{msg_type}]")
            try:
                import roslib.message
                msg_class = roslib.message.get_message_class(msg_type)
                if msg_class is not None:
                    full_text = msg_class._full_text if hasattr(msg_class, '_full_text') else ""
                    if full_text:
                        lines = full_text.split("\n")
                        for line in lines:
                            if line.startswith("=="):
                                break
                            if line.strip():
                                logger.info(f"    {line}")
                    else:
                        slots = getattr(msg_class, '__slots__', [])
                        types = getattr(msg_class, '_slot_types', [])
                        for s, t in zip(slots, types):
                            logger.info(f"    {t} {s}")
                else:
                    logger.error("(could not load message class)")
            except Exception as e:
                logger.error(f"(error getting description: {e})")
            logger.info("")

    # VerifySensors::run_api_verification will perform the verification of all sensors via the AirSim Python API, 
    # including checking accessibility and measuring frequencies.
    # \param[in] duration Duration in seconds to perform frequency measurement for each sensor [float]
    # \return True if all sensors were accessible via the API, False otherwise [bool]
    def run_api_verification(self, duration: float) -> bool:
        logger.info(self._separator("VERIFICATION VIA AIRSIM PYTHON API"))
        logger.info(f"\nConnecting to AirSim (vehicle: {self.vehicle_name})...")

        client = airsim.MultirotorClient()
        try:
            client.confirmConnection()
            logger.info("Connection established.\n")
        except Exception as e:
            logger.error(f"Could not connect to AirSim: {e}")
            return False

        # Verify each sensor type using consolidated configurations
        sensor_configs = self._build_sensor_verification_configs()
        total_ok = 0
        total_fail = 0

        for group_name, sensor_class, sensor_names in sensor_configs:
            results = sensor_class.verify_api_data(client, sensor_names, self.vehicle_name)
            group_totals = self._report_sensor_group_results(group_name, results)
            total_ok += group_totals["ok"]
            total_fail += group_totals["fail"]

        # Measure frequencies
        logger.info(self._separator("API SAMPLING FREQUENCY"))
        logger.info(f"Measuring for {duration}s...\n")

        frequencies = self._measure_api_frequency(client, duration)
        logger.info(f"{'Sensor':<40} {'Poll Rate (Hz)':<15} {'Update Rate (Hz)':<18} {'Samples/s':<12}")
        logger.info("-" * 90)
        for name, freq_data in frequencies.items():
            logger.info(
                f"{name:<40} {freq_data['api_poll_rate_hz']:<15.1f} "
                f"{freq_data['sensor_update_hz']:<18.1f} {freq_data['unique_samples_per_sec']:<12.1f}"
            )

        # Summary
        logger.info(self._separator("API SUMMARY"))
        logger.info(f"  Accessible sensors:   {total_ok}")
        logger.info(f"  Inaccessible sensors: {total_fail}")
        logger.info(f"  Total:                 {total_ok + total_fail}")

        return total_fail == 0

    # VerifySensors::run_ros_verification will perform the verification of all sensors via ROS topics, including 
    # checking for topic presence and measuring publishing frequencies.
    # \param[in] duration Duration in seconds to perform frequency measurement for each topic [float]
    # \return True if all expected ROS topics were found, False otherwise [bool]
    def run_ros_verification(self, duration: float) -> bool:
        try:
            import rospy
            import rostopic
        except ImportError:
            logger.warning("rospy not available. Run inside the AirSim container with ROS.")
            logger.warning("Use --api-only to verify only the AirSim API.")
            return False

        logger.info(self._separator("VERIFICATION VIA ROS TOPICS"))
        ros_topics = self._build_ros_topics()

        # Verify that ROS master is available
        try:
            rospy.init_node("VerifySensors", anonymous=True, disable_signals=True)
        except Exception as e:
            logger.error(f"Could not connect to ROS master: {e}")
            return False

        # Verify presence of expected topics
        topic_results = self._verify_topics(ros_topics, rostopic)
        topics_found = topic_results["topics_found"]
        topics_missing = topic_results["topics_missing"]
        discovered_types = topic_results["discovered_types"]

        # Print description of discovered message types
        self._report_discovered_message_types(discovered_types)

        # Measure topic frequencies
        logger.info(self._separator("ROS TOPIC PUBLISHING FREQUENCY"))
        logger.info(f"Measuring for {duration}s...\n")

        topic_counters: Dict[str, List[float]] = defaultdict(list)

        def make_callback(topic_name):
            def callback(_msg):
                topic_counters[topic_name].append(time.perf_counter_ns())
            return callback

        subscribers = []
        representative_sensors = self._build_representative_sensor_registry()

        for sensor_data in representative_sensors.values():
            topic = sensor_data["topic"]
            try:
                sub = rospy.Subscriber(topic, rospy.AnyMsg, make_callback(topic))
                subscribers.append(sub)
            except Exception as e:
                logger.warning(f"Could not subscribe to {topic}: {e}")

        # Wait for duration seconds while callbacks collect messages
        start_ns = time.perf_counter_ns()
        duration_ns = int(duration * 1e9)
        while (time.perf_counter_ns() - start_ns) < duration_ns and not rospy.is_shutdown():
            try:
                rospy.sleep((duration_ns - (time.perf_counter_ns() - start_ns)) / 1e9)
            except rospy.ROSInterruptException:
                logger.warning("ROS sleep interrupted during measurement window.")
                break

        # Unsubscribe
        for sub in subscribers:
            sub.unregister()

        # Calculate frequencies
        logger.info(f"{'Sensor':<40} {'Poll Rate (Hz)':<15} {'Update Rate (Hz)':<18} {'Samples/s':<12}")
        logger.info("-" * 90)

        for sensor_data in representative_sensors.values():
            topic = sensor_data["topic"]
            sensor_name = sensor_data["sensor_name"]
            timestamps = topic_counters.get(topic, [])
            count = len(timestamps)
            if count > 1:
                elapsed_ns = timestamps[-1] - timestamps[0]
                elapsed_s = elapsed_ns / 1e9
                freq = (count - 1) / elapsed_s if elapsed_s > 0 else 0
                samples_per_sec = count / elapsed_s if elapsed_s > 0 else 0
            else:
                freq = 0
                samples_per_sec = 0
            logger.info(f"{sensor_name:<40} {samples_per_sec:<15.1f} {freq:<18.1f} {samples_per_sec:<12.1f}")

        # Show last received data for content verification
        logger.info("\n--- Last raw data received (sample) ---")
        logger.info("(Raw data is shown in the API section above)")

        # Summary
        logger.info(self._separator("ROS SUMMARY"))
        logger.info(f"Topics found: {topics_found}")
        logger.info(f"Topics missing:   {topics_missing}")
        logger.info(f"Total expected:    {topics_found + topics_missing}")

        rospy.signal_shutdown("Verification completed")
        return topics_missing == 0

    # VerifySensors::run will execute the full verification process, including both API and ROS checks based on the specified mode.
    # \param[in] api_only If True, only perform API verification [bool]
    # \param[in] ros_only If True, only perform ROS verification [bool]
    # \param[in] duration Duration in seconds to perform frequency measurement for each sensor/topic [float]
    # \return True if all sensors were verified successfully, False otherwise [bool]
    def run(self, api_only: bool = False, ros_only: bool = False, duration: float = 5.0) -> bool:
        logger.info("VerifySensors - AirSim sensor verification")
        logger.info(f"Vehicle: {self.vehicle_name}")
        logger.info(f"Measurement duration: {duration}s")
        logger.info(f"Mode: {'API only' if api_only else 'ROS only' if ros_only else 'API + ROS'}")
        logger.info(f"{'#'*70}")

        api_ok = True
        ros_ok = True

        if not ros_only:
            api_ok = self.run_api_verification(duration)

        if not api_only:
            ros_ok = self.run_ros_verification(duration)

        # Final result
        logger.info(self._separator("FINAL RESULT"))
        if api_ok and ros_ok:
            logger.info("ALL SENSORS VERIFIED SUCCESSFULLY")
            return True
        else:
            if not api_ok:
                logger.error("Some sensors not accessible via API")
            if not ros_ok:
                logger.error("Some ROS topics not available")
            return False


def main():
    logger.remove()
    logger.add(sys.stderr, level="INFO")
    parser = argparse.ArgumentParser(
        description="AirSim sensor verification for Veronte vehicle"
    )
    parser.add_argument(
        "--api-only",
        action="store_true",
        help="Only verify via AirSim Python API (no ROS)",
    )
    parser.add_argument(
        "--ros-only",
        action="store_true",
        help="Only verify via ROS topics (requires rospy)",
    )
    parser.add_argument(
        "--duration",
        type=float,
        default=120.0,
        help="Duration in seconds to measure frequencies (default: 120s)",
    )
    parser.add_argument(
        "--vehicle",
        type=str,
        default=DEFAULT_VEHICLE_NAME,
        help=f"AirSim vehicle name (default: {DEFAULT_VEHICLE_NAME})",
    )
    args = parser.parse_args()

    verifier = VerifySensors(args.vehicle)
    success = verifier.run(
        api_only=args.api_only,
        ros_only=args.ros_only,
        duration=args.duration
    )
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    
    main()
