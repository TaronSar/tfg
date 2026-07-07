#!/bin/bash
set -e

# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

roslaunch ual_backend_mavros server.launch autopilot:=px4 mode:=custom fcu_url:=udp://:14550@localhost:14556 --wait
