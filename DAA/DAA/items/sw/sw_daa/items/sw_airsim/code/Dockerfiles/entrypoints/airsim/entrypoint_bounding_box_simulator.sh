#!/bin/bash
set -e

source "/opt/ros/$ROS_DISTRO/setup.bash"
python3 -u /root/settings/segmentation_dataset_builder.py