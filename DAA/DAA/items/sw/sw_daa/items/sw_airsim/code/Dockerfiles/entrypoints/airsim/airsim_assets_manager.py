#!/usr/bin/env python3
# https://microsoft.github.io/AirSim/api_docs/html/_modules/airsim/client.html


from __future__ import annotations
import airsim
from airsim.utils import to_quaternion, to_eularian_angles, Quaternionr

import numpy as np

import time
import rospy
from geometry_msgs.msg import PoseStamped
import threading
import math
import yaml
from loguru import logger

TIME_RESOLUTION = 1.0/60.0
Z_SPAWN_OFFSET = -1.0
MARKER_COMPILED_SIZE = 0.5
TEXTURES_PATH = "/home/catec/textures/"
UAV_HEIGHT = 0.3
PUBLISHER_FRAME_ID = "global"
UAL_POSE_TOPIC = "/uav_0/ual/pose"
UAV_MAIN_UAV = "uav_sens"
SYNC_START_PARAM = "/airsim/wp1_start_time"             # start time is sent from track_waypoints.py when UAV approaches wp_1
OBJECTS_FINISHED_PARAM = "/airsim/objects_finished"     # set to true when all objects have finished
THRESHOLD_DISTANCE_WAYPOINT_REACHED = 3.0
HIDE_POSITION = [0, 0, -100]
HIDE_EA = [0, 0, 0]


# AirsimAssetsManager will configure environment in Unreal Engine using AirSim API.
class AirsimAssetsManager:
    # AirsimAssetsManager::__init will initialize the AirSim client and class variables
    def __init__(self) -> None:
        client = airsim.VehicleClient()
        client.confirmConnection()
        self.__client = client
        self.__available_assets = self.__client.simListAssets()
        self.__frame_id =  PUBLISHER_FRAME_ID
        self.__mutex = threading.Lock()

    # AirsimAssetsManager::close will close the AirSim client connection
    def close(self):
        try:
            if self.__client is not None:
                logger.info("airsim_assets_manager: Closing AirSim client...")
                self.__client = None
                logger.info("airsim_assets_manager: AirSim client closed")
        except Exception as e:
            logger.warning(f"airsim_assets_manager: Warning - error closing client: {e}")


    # AirsimAssetsManager::fleet_simulator_callback will move the dummy UAVs in AirSim according to the pose received from the fleet simulator through ROS topics
    def fleet_simulator_callback(self, data: PoseStamped, dummy_uav_key: str):
        logger.debug(f"Received pose for {dummy_uav_key}: {data.pose.position.x}, {data.pose.position.y}, {data.pose.position.z}")
        position = [data.pose.position.x, data.pose.position.y, data.pose.position.z + Z_SPAWN_OFFSET]
        quaternion = Quaternionr()
        quaternion.x_val = data.pose.orientation.x
        quaternion.y_val = data.pose.orientation.y
        quaternion.z_val = data.pose.orientation.z
        quaternion.w_val = data.pose.orientation.w
        orientation = to_eularian_angles(quaternion)
        orientation = [np.rad2deg(orientation[0]), np.rad2deg(orientation[1]), np.rad2deg(orientation[2]) - 90]
        self.move_object_to_position(dummy_uav_key, position, orientation)
        
    
    # AirsimAssetsManager::spawn_object will spawn an airsim object.
    def spawn_object(self, object_name: str, object_type: str, position: list[float], ea_deg: list[float], scale_vector: list[float] = [1,1,1]) -> bool:

        if object_type not in self.__available_assets:
            logger.warning(f"Object type '{object_type}' not available")
            return False

        pose = airsim.Pose()
        pose.position = airsim.Vector3r(position[0], -position[1], -position[2])
        pose.orientation = to_quaternion(roll=ea_deg[0], pitch=-ea_deg[1], yaw=-ea_deg[2])

        scale = airsim.Vector3r(scale_vector[0], scale_vector[1], scale_vector[2])

        success = self.__client.simSpawnObject(object_name, object_type, pose, scale)

        if (not success):
            logger.warning(f"Spawn not fixed for: {object_name}")
            return success
        
        logger.info(f"Spawned object '{object_name}' with type: {object_type} in position: {position} with orientation: {ea_deg}")
        return success
    

    # AirsimAssetsManager::set_texture will set the texture to an airsim object.
    def set_texture(self, object_name: str, texture_path: str) -> bool:
        success = self.__client.simSetObjectMaterialFromTexture(object_name, TEXTURES_PATH +texture_path)
        if (not success):
            logger.warning(f"Texture not fixed for: {object_name}")
            return success
        
        logger.info(f"Set texture '{texture_path}' to object '{object_name}'")
        return success


    # AirsimAssetsManager::move_object_to_position will move AirSim object to specified 6DoF pose.
    def move_object_to_position(self, object_name: str, desired_position: list[float], desired_ea_deg: list[float]) -> bool:
        with self.__mutex:
            curr_pose = self.__client.simGetObjectPose(object_name)
            if (curr_pose.containsNan()):
                logger.warning(f"Unable to get object: {object_name}")
                return False
            
            desired_ea_rad = np.deg2rad(desired_ea_deg)

            # add 90 deg to yaw to match airsim coordinate system
            desired_ea_rad[2] += np.pi/2

            pose = airsim.Pose()
            pose.position = airsim.Vector3r(desired_position[0], -desired_position[1], -desired_position[2])
            pose.orientation = to_quaternion(roll=desired_ea_rad[1], pitch=-desired_ea_rad[0], yaw=-desired_ea_rad[2])

            # NOTE: Here we move with teleport enabled so collisions are ignored
            success = self.__client.simSetObjectPose(object_name, pose, teleport=True)
            
            return success
        
    
    # AirsimAssetsManager::scale_object will modify the scale of an AirSim object. Useful for markers.
    def scale_object(self, object_name: str, scale_vector: list[float]) -> bool:
        curr_pose = self.__client.simGetObjectScale(object_name)
        if (curr_pose.containsNan()):
            logger.warning(f"Unable to get object: {object_name}")
            return False
        
        scale = airsim.Vector3r(scale_vector[0], scale_vector[1], scale_vector[2])
        success = self.__client.simSetObjectScale(object_name, scale)
        if (not success):
            logger.warning(f"Scale not fixed for: {object_name}")
            return success
        
        logger.debug(f"Scaled object '{object_name}' to scale: {scale_vector}")
        return success


    # AirsimAssetsManager::move_object_by_path will move AirSim object by a predefined path.
    # Path format: [x, y, z] or [x, y, z, roll_deg, pitch_deg, yaw_deg]
    def move_object_by_path(self, object_name: str, path_array: list[list[float]], sleep_time: float) -> None:
        for idx, pose in enumerate(path_array):
            # Check if pose has at least 3 elements for position
            if len(pose) < 3:
                logger.warning(f"Invalid pose length at index {idx}: expected at least 3 elements (got {len(pose)})")
                return
            
            # Stores position and orientation (if provided)
            position = np.array([pose[0], pose[1], pose[2]])
            ea = np.array([pose[3], pose[4], pose[5]]) if len(pose) >= 6 else np.array([0.0, 0.0, 0.0])
            
            time.sleep(sleep_time)
            
            # Moves object to target position and checks if it fails
            if not self.move_object_to_position(object_name, position, ea):
                logger.error("Some error happen during movement")
                return

    # distance_to_point will calculate the distance between the current pose of an object and a target position
    def distance_to_point(self, current_pose: PoseStamped, target_position: list[float]) -> float:
        dx = current_pose.pose.position.x - target_position[0]
        dy = current_pose.pose.position.y - target_position[1]
        dz = current_pose.pose.position.z - target_position[2]
        return math.sqrt(dx*dx + dy*dy + dz*dz)

    # wait_for_wp0_approach will wait for UAV to approach wp_1 from default.yaml
    def wait_for_wp0_approach(self) -> bool:
        try:
            # Read default.yaml from container path
            yaml_file_path = "/root/settings/trajectories/default.yaml"
            
            with open(yaml_file_path, 'r') as f:
                wp_data = yaml.safe_load(f)
            
            # Checks if wp_1 exists
            if 'wp_1' not in wp_data:
                logger.warning("wp_1 not found in waypoints file")
                return False
            
            # Extracts wp_1 position
            wp_1_position = wp_data['wp_1'][:3]  # Extract x, y, z
            current_pose = [None]
            
            # Callback function to update current pose
            def pose_callback(msg):
                current_pose[0] = msg
            
            # Subscribe to pose topic, updating current_pose in consequence
            subscriber = rospy.Subscriber(UAL_POSE_TOPIC, PoseStamped, pose_callback)
            
            logger.info(f"Waiting for UAV to approach wp_1 [{wp_1_position[0]:.2f}, {wp_1_position[1]:.2f}, {wp_1_position[2]:.2f}]...")
            
            start_time = time.time()
            timeout = 300  # 5 minutes timeout
            
            # While ROS is active and timeout not reached
            while not rospy.is_shutdown() and (time.time() - start_time) < timeout:
                # When it has received a pose, computes distance to wp_1 and checks if it is within threshold
                if current_pose[0] is not None:
                    distance = self.distance_to_point(current_pose[0], wp_1_position)
                    # When it is within distance threshold, unregister and return true
                    if distance < THRESHOLD_DISTANCE_WAYPOINT_REACHED:  # Within threshold distance
                        logger.info("UAV reached wp_1. Starting object movement.")
                        subscriber.unregister()
                        return True
                rospy.sleep(0.5)
            
            # Not reached within timeout, unregister and return false
            logger.warning("Timeout waiting for UAV to approach wp_1")
            subscriber.unregister()
            return False
        except Exception as e:
            logger.error(f"Error waiting for wp_1 approach: {e}")
            return False


    # AirsimAssetsManager::move_objects will move AirSim objects by predefined paths.
    # Path format: [x, y, z, roll_deg, pitch_deg, yaw_deg]
    def move_objects(self, data: dict, time_resolution: float, publishers: dict | None = None, wp0_yaml_path: str | None = None):
        indexes = {}
        
        # Creates a indexes dictionary, one per object, initialized to 0 (first waypoint)
        for object_name in data:
            indexes[object_name] = 0
            object_data = data[object_name]
            virtual_object = bool(object_data.get("virtual", False))

            if virtual_object:
                logger.info(f"Object '{object_name}' configured as virtual (no AirSim mesh spawn)")
            else:
                logger.info(f"Object '{object_name}' is already spawned")
        
        # Wait for UAV to approach wp_1 before moving objects
        if not self.wait_for_wp0_approach():
            logger.warning("Failed to wait for wp_1 approach, continuing anyway")
            
        logger.info("Moving dynamic objects...")
        # Start elapsed-time counter only when wp_1 is actually reached in track_waypoints.
        while not rospy.is_shutdown() and not rospy.has_param(SYNC_START_PARAM):
            rospy.sleep(0.05)

        if rospy.is_shutdown():
            return

        # Stores start time
        scenario_start_time = float(rospy.get_param(SYNC_START_PARAM))
        logger.info(f"Using synchronized start time from {SYNC_START_PARAM}: {scenario_start_time:.3f}")
        
        # Infinite loop iterating through all the objects
        while True:
            # Computes elapsed time
            elapsed = rospy.get_time() - scenario_start_time
            next_check_sleep = None

            # For all dynamic objects
            for object_name in data:
                if (indexes[object_name] < 0):
                    continue

                # Path of current object
                path = data[object_name]["path"]
                if len(path) == 0:
                    indexes[object_name] = -1
                    continue

                object_time_offset = data[object_name].get("time_offset")
                object_elapsed = elapsed

                # Handle time_offset before starting movement
                if object_time_offset is not None:
                    # If time offset has not been reached yet
                    if elapsed < object_time_offset:
                        # Computes missing time to reach it
                        remaining_offset = object_time_offset - elapsed
                        if next_check_sleep is None or remaining_offset < next_check_sleep:
                            next_check_sleep = remaining_offset
                        # Moves object to initial position (first waypoint) until time offset is reached
                        pose = path[0]
                        position = np.array([pose[0], pose[1], pose[2]])
                        ea = np.array([pose[3], pose[4], pose[5]]) if len(pose) >= 6 else np.array([0.0, 0.0, 0.0])
                        self.move_object_to_position(object_name, position, ea)
                        if publishers != None:
                            self.publish_pose(publishers[object_name], position, ea)
                        continue
                    object_elapsed = elapsed - object_time_offset

                # Current waypoint to execute.
                current_index = indexes[object_name]
                # If current index is greater than path length
                if current_index >= len(path):
                    # If is cyclic, restart from the beginning of the path
                    if data[object_name]["cyclic"]:
                        indexes[object_name] = 0
                        current_index = 0
                    # Otherwise, mark as finished with -1 index and optionally hide it
                    else:
                        indexes[object_name] = -1
                        logger.info(f"Finished movement of object '{object_name}'")
                        if data[object_name].get("hide_when_finished") == True:
                            self.move_object_to_position(object_name, HIDE_POSITION, HIDE_EA)
                        # Check if all objects have finished and notify it
                        if all(v < 0 for v in indexes.values()):
                            logger.info(f"All objects finished. Setting {OBJECTS_FINISHED_PARAM}")
                            rospy.set_param(OBJECTS_FINISHED_PARAM, True)
                        continue

                # Read current waypoint and its time
                current_waypoint = path[current_index]
                current_wp_time = current_waypoint[6] if len(current_waypoint) > 6 else None

                # If waypoint time has not been reached yet, sleep until it should be executed.
                if current_wp_time is not None and object_elapsed < current_wp_time:
                    remaining_wp = current_wp_time - object_elapsed
                    if next_check_sleep is None or remaining_wp < next_check_sleep:
                        next_check_sleep = remaining_wp
                    continue

                # Time reached: execute current waypoint and advance to next one.
                pose = current_waypoint
                position = np.array([pose[0], pose[1], pose[2]])
                ea = np.array([pose[3], pose[4], pose[5]]) if len(pose) >= 6 else np.array([0.0, 0.0, 0.0])

                if not bool(data[object_name].get("virtual", False)):
                    self.move_object_to_position(object_name, position, ea)
                if publishers != None:
                    self.publish_pose(publishers[object_name], position, ea)

                logger.info(f"Waypoint {current_index} reached for object '{object_name}' at t={object_elapsed:.2f}s")
                indexes[object_name] = current_index + 1

            # Sleep until the next scheduled event to avoid busy polling.
            if next_check_sleep is not None and next_check_sleep > 0:
                rospy.sleep(next_check_sleep)
            else:
                rospy.sleep(time_resolution)

    # AirsimAssetsManager::publish_pose will publish the pose of an object to a ROS topic. This is used to publish the pose of the dummy UAVs to the fleet simulator.
    def publish_pose(self, publisher: rospy.Publisher, position: list[float], ea_deg: list[float]):
        ea_rad = np.deg2rad(ea_deg)
        quaterion = to_quaternion(roll=ea_rad[0], pitch=ea_rad[1], yaw=ea_rad[2])
        ros_msg = PoseStamped()
        ros_msg.header.frame_id = self.__frame_id
        ros_msg.pose.position.x = position[0]
        ros_msg.pose.position.y = position[1]
        ros_msg.pose.position.z = position[2] - Z_SPAWN_OFFSET
        ros_msg.pose.orientation.x = quaterion.x_val
        ros_msg.pose.orientation.y = quaterion.y_val
        ros_msg.pose.orientation.z = quaterion.z_val
        ros_msg.pose.orientation.w = quaterion.w_val
        publisher.publish(ros_msg)
