#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

rosrun uav_abstraction_layer track_waypoints.py -plan_file /root/trajectories/${UAL_TRAJECTORY_FILE}