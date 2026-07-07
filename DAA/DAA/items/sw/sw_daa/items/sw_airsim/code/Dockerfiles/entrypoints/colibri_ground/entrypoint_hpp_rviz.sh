#!/bin/bash
set -e
source "/opt/ros/$ROS_DISTRO/setup.bash"

rosrun rviz rviz -d /opt/ros/noetic/share/rviz/planners.rviz