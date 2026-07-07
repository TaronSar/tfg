#!/bin/bash
set -e

source "/opt/ros/$ROS_DISTRO/setup.bash"
python3 airsim_simulation_runner.py $MAIN_UAV_NAME