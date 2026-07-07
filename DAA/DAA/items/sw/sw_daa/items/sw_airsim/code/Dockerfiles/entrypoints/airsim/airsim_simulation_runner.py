#!/usr/bin/env python3
# https://microsoft.github.io/AirSim/api_docs/html/_modules/airsim/client.html

from __future__ import annotations
from airsim_assets_manager import AirsimAssetsManager
import sys
from typing import Callable
import numpy as np
import matplotlib.pyplot as plt
import json
import os
import rospy
from geometry_msgs.msg import PoseStamped
from loguru import logger

TIME_RESOLUTION = 1.0/60.0
Z_SPAWN_OFFSET = -1.0
MARKER_COMPILED_SIZE = 0.5
TEXTURES_PATH = "/home/catec/textures/"
UAV_HEIGHT = 0.3
PUBLISHER_FRAME_ID = "global"
UAV_MAIN_UAV = "uav_sens"



# generate_smooth_positions will generate the 3D positions smoothly from the waypoints.
# \param [in] waypoints List of desired waypoints [x, y, z] [m, m, m]
# \param [in] acceleration acceleration's module in velocities adaptation [m/s^2]
# \param [in] cruising_speed module of the desired cruising speed [m/s]
# \param [in] time_resolution time resolution of the trajectory [s]
# \return trajectory [x, y, z] [m, m, m]
def generate_smooth_positions(waypoints: np.ndarray, cruising_speed: float, acceleration: float, time_resolution: float) -> np.ndarray:

    # duplicate first and last waypoint 
    waypoints = np.vstack((waypoints[0], waypoints))
    waypoints = np.vstack((waypoints, waypoints[-1]))

    logger.info(f"Waypoints: {waypoints}")

    # time for each waypoint considering the crusing speed & acceleration
    time_waypoints = []
    time_waypoints.append(0)

    for i in range(len(waypoints)-1):
        dist = np.linalg.norm(np.array(waypoints[i+1][:]) - np.array(waypoints[i][:]))
        if dist != 0:
            dist_required = cruising_speed**2/acceleration
            if dist > dist_required:
                time_waypoints.append(time_waypoints[i] + dist/cruising_speed)
            else:
                time_waypoints.append(time_waypoints[i] + 2*np.sqrt(dist/acceleration))
        else:
            time_waypoints.append(time_waypoints[i] + cruising_speed/acceleration)

    # interpolation data: precalculating parameters for each section
    # a section is defined as: linear interpolation + cuadratic interpolation between three points

    t0  = []; t1  = []; t2   = []
    p0  = []; p1  = []; p2   = []
    v01 = []; v12 = []; a012 = []
    tau = [0]

    for i in range(len(waypoints)-2):

        t0.append(time_waypoints[i])
        t1.append(time_waypoints[i+1])
        t2.append(time_waypoints[i+2])

        p0.append(np.array(waypoints[i][:]))
        p1.append(np.array(waypoints[i+1][:]))
        p2.append(np.array(waypoints[i+2][:]))

        v01.append((p1[i]-p0[i])/(t1[i]-t0[i]))
        v12.append((p2[i]-p1[i])/(t2[i]-t1[i]))

        a12dir = v12[i] - v01[i]
        if np.linalg.norm(a12dir) != 0:
            a12dir = a12dir/np.linalg.norm(a12dir)
        a012.append(acceleration*a12dir)

        if a012[i][0] != 0:
            tau.append(0.5*(v12[i][0] - v01[i][0])/a012[i][0])
        elif a012[i][1] != 0:
            tau.append(0.5*(v12[i][1] - v01[i][1])/a012[i][1])
        elif a012[i][2] != 0:
            tau.append(0.5*(v12[i][2] - v01[i][2])/a012[i][2])
        else:
            tau.append(0)

    n_sections = len(a012)

    # run-time interpolation simulation
    time = np.arange(0, time_waypoints[-1], time_resolution) #s
    p = []

    for t in time:
        k = -1
        for i in range(n_sections):
            if t >= (t0[i] + tau[i]) and t < (t1[i] + tau[i+1]):
                k = i 
                break

        if k != -1:
            # linear interpolation
            if t < t1[k] - tau[k+1]:
                pos = p0[k] + v01[k]*(t - t0[k])
                p.append([pos[0], pos[1], pos[2]])

            # cuadratic interpolation
            else:
                pos = p1[k] + v01[k]*(t - t1[k]) + 0.5* a012[k] * pow((t - t1[k]+ tau[k+1]),2)
                p.append([pos[0], pos[1], pos[2]])

            continue

        # before the first section
        if t < t0[0] + tau[0]:
            p.append([p0[0][0], p0[0][1], p0[0][2]])

        # after the last section
        elif t >= t1[-1] + tau[-1]:
            p.append([p2[-1][0], p2[-1][1], p2[-1][2]])

        # error
        else:
            logger.error(f"Error: t = {t} is not a valid time")
    
    return p


# generate_orientations will generate the 3D orientations to a given set of positions. To generate this, each pair of consecutive positions are
# taking into account:
# - Walker TYPE: yaw and pitch, X axis will aim to the next waypoint [FLU system]
# - Drone TYPE: yaw will be a constant and roll and pitch will be proportional to the velocity XY vector
# \param [in] p List of positions [x, y, z, t] [m, m, m, s]
# \param [in] type Type of object to generate the orientation. Available: "walker"; "drone"
# \return List of associated orientations [roll, pitch, yaw] [deg, deg, deg]
def generate_orientations(p: np.ndarray, type: str = "walker") -> np.ndarray:
    orientations = []

    if type == "walker" :
        for i in range(len(p)-1):

            dir = np.array([p[i+1][0],p[i+1][1],p[i+1][2]]) - np.array([p[i][0],p[i][1],p[i][2]])

            if np.linalg.norm(dir) != 0: 
                dir = dir/np.linalg.norm(dir)

                # yaw & pitch : x axis (FLU) pointing next one
                yaw   = np.arctan2(dir[1], dir[0])*180/np.pi
                pitch = -1*np.arctan2(dir[2], np.sqrt(dir[0]**2 + dir[1]**2))*180/np.pi
                roll  = 0
                orientations.append([roll, pitch, yaw])
                continue
        
            # no movement between two points
            if i == 0:
                # get the orientation to the first movement point
                for j in range(len(p)):
                    dir = np.array([p[j][0],p[j][1],p[j][2]]) - np.array([p[0][0],p[0][1],p[0][2]])
                    if np.linalg.norm(dir) != 0:
                        dir   = dir/np.linalg.norm(dir)
                        yaw   = np.arctan2(dir[1], dir[0])*180/np.pi
                        pitch = -1*np.arctan2(dir[2], np.sqrt(dir[0]**2 + dir[1]**2))*180/np.pi
                        roll  = 0
                        orientations.append([roll, pitch, yaw])
                        break
                if j == (len(p)-1):
                    orientations.append([0, 0, 0])
            else:
                orientations.append(orientations[-1])

    elif type == "drone" :
        ## adjustable paramaters
        MAX_VEL_RATE = 1   # maximum velocity [m/s]
        MIN_VEL_RATE = -1  # minimun velocity [m/s]
        MAX_TILT  = 15   # maximum tilt [deg]
        MIN_TILT  = -15  # minimun tilt [deg]

        for i in range(len(p)-1):
            dir = (np.array([p[i+1][0],p[i+1][1]]) - np.array([p[i][0],p[i][1]]))/(TIME_RESOLUTION)
            if np.linalg.norm(dir) == 0:
                orientations.append([0, 0, 0])
                continue
            
            roll  =  np.interp(dir[0],[MIN_VEL_RATE, MAX_VEL_RATE],[MIN_TILT, MAX_TILT])
            pitch =  np.interp(dir[1],[MIN_VEL_RATE, MAX_VEL_RATE],[MIN_TILT, MAX_TILT])
            yaw   = 0
            orientations.append([roll, pitch, yaw])

    # extend the orientation to the last point
    orientations.append(orientations[-1])
    return orientations

# plot_trajectory will plot the trajectory in 3D and save the plot in the assets/graphs folder with the name of the object. This is useful to debug the generated trajectories.
def plot_trajectory(positions: np.ndarray, waypoints: np.ndarray):
    fig = plt.figure()
    ax = fig.add_subplot(111, projection='3d')
    ax.set_xlabel('Y')
    ax.set_ylabel('X')
    ax.set_zlabel('Z')
    x_range = np.ptp(np.array(positions)[:,0])
    y_range = np.ptp(np.array(positions)[:,1])
    z_range = np.ptp(np.array(positions)[:,2])
    if x_range == 0:
        x_range = 0.1
    if y_range == 0:    
        y_range = 0.1
    if z_range == 0:
        z_range = 0.1
    ax.set_box_aspect((x_range, y_range, z_range))
    ax.plot(np.array(positions)[:,0], np.array(positions)[:,1], np.array(positions)[:,2],'c-')
    ax.plot(np.array(waypoints)[:,0], np.array(waypoints)[:,1], np.array(waypoints)[:,2],'ro', markersize=2)

# generate_smooth_trayectories will generate the trajectories for each object.
# \param [in] data Dictionary with the data of each object
# \param [in] type Type of object to generate the trajectory. Available: "walker"; "drone".
# \return Dictionary with the data of each object including the trajectory
def generate_smooth_trayectories(data: dict, type: str = "walker"):

    # Generate Trajectories for each object
    for object_name in data:
        object_data = data[object_name]

        # Generate Trajectory
        waypoints = object_data["waypoints"]
        cruising_speed = object_data["velocity"]
        acceleration = object_data["acceleration"]

        # If waypoint time is provided ([x, y, z, roll, pitch, yaw, time]),
        # preserve it directly so runtime scheduling is driven by that timestamp.
        if len(waypoints) > 0 and len(waypoints[0]) >= 7:
            path = []
            for waypoint in waypoints:
                path.append([
                    waypoint[0],
                    waypoint[1],
                    waypoint[2] + Z_SPAWN_OFFSET,
                    waypoint[3],
                    waypoint[4],
                    waypoint[5],
                    waypoint[6],
                ])
            object_data["path"] = path
            continue
        
        logger.debug(f"Object: {object_name}")
        logger.debug(f"Waypoints: {waypoints}")
        logger.debug(f"Waypoint length: {len(waypoints[0]) if waypoints else 0}")
        logger.debug(f"Cruising Speed: {cruising_speed}")
        logger.debug(f"Acceleration: {acceleration}")

        # This part generates trajectories with input waypoints 
        # Add Z offset to waypoints
        waypoints = [[waypoint[0], waypoint[1], waypoint[2] + Z_SPAWN_OFFSET] for waypoint in waypoints]

        # Generate Trajectory
        positions = generate_smooth_positions(waypoints, cruising_speed, acceleration, TIME_RESOLUTION)
        orientations = generate_orientations(positions, type = type)
        path = [[positions[i][0], positions[i][1], positions[i][2], orientations[i][0], orientations[i][1], orientations[i][2]] for i in range(len(positions))]
        object_data["path"] = path
        
        # Save a plot of the trajectories in 3D
        plot_trajectory(positions, waypoints)
        
        plt.title(f"\n\nTrajectory of {object_name}. \nAccel: {acceleration} m/s^2 Velocity: {cruising_speed} m/s \n Cyclic: {object_data['cyclic']}")
        plt.subplots_adjust(top=0.85)
        plt.savefig('assets/graphs/' + object_name + '.png')


# place_markers will place the markers in the environment. Markers are static objects that can be used to identify the position of interest in the environment.
def place_markers(data: dict, manager: AirsimAssetsManager):
    for marker_name in data:
        marker_data = data[marker_name]
        position = marker_data["position"]
        position = [position[0], position[1], position[2] + Z_SPAWN_OFFSET]
        scale = [marker_data["size"]/MARKER_COMPILED_SIZE, marker_data["size"]/MARKER_COMPILED_SIZE, 1.0]
        ea = marker_data["orientation"]

        # Spawn marker
        if marker_data.get("type") != "" and marker_data.get("type") != None:
            manager.spawn_object(marker_name, marker_data.get("type"), position, ea, scale)

        # Move marker if it is already spawned (type empty)
        else :
            manager.move_object_to_position(marker_name, position, ea)
            manager.scale_object(marker_name, scale)

        # Set texture
        texture_path = marker_data.get("texture")
        if texture_path != "" and texture_path != None:
            manager.set_texture(marker_name, texture_path)


# parse_dummy_uavs_data will parse the dummy UAVs data from the configuration file and generate the waypoints for each dummy UAV. The waypoints are generated by adding a takeoff point at the beginning and a landing point at the end of the route.
def parse_dummy_uavs_data(data: dict, id_base_name: str = "dummyDrone") -> dict:
    dummy_assets_data = {}
    for ind, dummy_name in enumerate(data):

        dummy_data = data[dummy_name]

        dummy_key = id_base_name + str(ind)

        dummy_assets_data[dummy_key] = {}

        dummy_assets_data[dummy_key]["waypoints"] = []

        first_wp = [ dummy_data["route"][0]["x"],  dummy_data["route"][0]["y"], UAV_HEIGHT/2.0]
        dummy_assets_data[dummy_key]["waypoints"].append(first_wp)

        for wp_dict in dummy_data["route"]:
            wp = [wp_dict["x"], wp_dict["y"], wp_dict["z"]]
            dummy_assets_data[dummy_key]["waypoints"].append(wp)

        last_wp = [ dummy_data["route"][-1]["x"],  dummy_data["route"][-1]["y"], UAV_HEIGHT/2.0]
        dummy_assets_data[dummy_key]["waypoints"].append(last_wp)

        dummy_assets_data[dummy_key]["cyclic"] = False
        if dummy_data.get("cyclic") != None:
            dummy_assets_data[dummy_key]["cyclic"] = dummy_data["cyclic"]

        dummy_assets_data[dummy_key]["velocity"] = dummy_data["max_vel"]
        dummy_assets_data[dummy_key]["acceleration"] = dummy_data["max_acc"]
        dummy_assets_data[dummy_key]["time_offset"] = dummy_data["takeoff_time"]
    
    return dummy_assets_data

# create_publishers will create a ROS publisher for each dynamic asset to publish its pose to the fleet simulator.
def create_publishers(dynamic_assets_data: dict) -> dict:
    publishers = {}
    for object_name in dynamic_assets_data:
        publishers[object_name] = rospy.Publisher('/airsim_node/' + object_name + '/pose', PoseStamped, queue_size=10)
    return publishers

# create_fleet_subscribers will create a ROS subscriber for each UAV in the fleet to receive its pose from the fleet simulator.
def create_fleet_subscribers(fleet_data: dict, dummy_callback: Callable[[PoseStamped, str], None], ur_base_name: str = "dummyDrone") -> dict:
    subscribers = {}
    for ind, uav_id in enumerate(fleet_data):

        # Ignore main UAV
        if uav_id == UAV_MAIN_UAV:
            continue

        dummy_uav_key = ur_base_name + str(ind)
        subscribers[dummy_uav_key] = rospy.Subscriber(uav_id + '/ual/pose', PoseStamped, dummy_callback, dummy_uav_key)
        logger.info(f"Subscribed to topic: {uav_id + '/pose'}")
    return subscribers

# main will execute the main loop of the AirSim assets manager.
def main():
    rospy.init_node('airsim_assets_manager', anonymous=True)

    if len(sys.argv) > 1:
        global UAV_MAIN_UAV
        UAV_MAIN_UAV = sys.argv[1]

    # Assets Graphs Folder
    if not os.path.exists('assets/graphs'):
        os.makedirs('assets/graphs')
    for file in os.listdir('assets/graphs'):
        if file.endswith('.png'):
            os.remove('assets/graphs/' + file)

    manager = AirsimAssetsManager()
    logger.info("Created AirsimAssetsManager!")

    # Read static.json file
    with open('settings/assets/static.json') as json_file:
        markers_data = json.load(json_file)
    place_markers(markers_data, manager) 
    
    # Read dynamic.json file
    with open('settings/assets/dynamic.json') as json_file:
        assets_data = json.load(json_file)
    generate_smooth_trayectories(assets_data, type = "walker")

    # Read dummy_uavs.json file
    with open('settings/assets/dummy_uavs.json') as json_file:
        dummy_uavs_data = json.load(json_file)

    dummy_assets_data = parse_dummy_uavs_data(dummy_uavs_data)
    generate_smooth_trayectories(dummy_assets_data, type = "drone")

    # Adding dummy drones to assets_data
    assets_data.update(dummy_assets_data)

    # Create publishers
    publishers = create_publishers(assets_data)

    # Read fleet.json file
    with open('settings/fleet.json') as json_file:
        fleet_json_data = json.load(json_file)
    fleet_subscribers = create_fleet_subscribers(fleet_json_data, manager.fleet_simulator_callback)

    # Move objects
    try:
        manager.move_objects(assets_data, TIME_RESOLUTION, publishers)
    finally:
        # Always close the client when done
        manager.close()

if __name__ == "__main__":
    main()