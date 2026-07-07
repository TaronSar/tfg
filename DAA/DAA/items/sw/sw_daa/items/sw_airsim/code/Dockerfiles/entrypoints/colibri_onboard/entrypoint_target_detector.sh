#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

roslaunch aruco_ros_detector aruco_detector_node.launch --wait