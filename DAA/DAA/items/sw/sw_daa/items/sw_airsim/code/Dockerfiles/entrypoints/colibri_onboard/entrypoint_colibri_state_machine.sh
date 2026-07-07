#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

roslaunch colibri_state_machine colibri_state_machine.launch takeoff_height:=2.0 v_cruise:=1.0 --wait