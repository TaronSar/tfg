#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

rosrun ual_teleop key_teleop.py --wait
