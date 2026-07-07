#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

rosrun uav_abstraction_layer save_waypoints.py -plan_folder /root/trajectories/
