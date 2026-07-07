#!/bin/bash
set -e

source "/opt/ros/$ROS_DISTRO/setup.bash"
python3 fleet_simulator.py $MAIN_UAV_NAME