#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

rosrun ual_teleop simulate_safety_pilot.py --wait
