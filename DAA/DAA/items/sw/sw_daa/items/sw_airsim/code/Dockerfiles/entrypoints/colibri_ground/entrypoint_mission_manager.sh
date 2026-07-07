#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"
source /root/fleet_manager_ws/devel/setup.bash

roslaunch colibri_fleet_manager mission_manager.launch --wait