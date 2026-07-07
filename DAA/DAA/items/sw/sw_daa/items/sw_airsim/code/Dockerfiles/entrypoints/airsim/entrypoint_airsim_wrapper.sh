#!/bin/bash
set -e


# setup ros environment
source "/opt/ros/$ROS_DISTRO/setup.bash"

# First argument is ground truth pose topic
ground_truth_pose_topic=$1

rosparam set /use_sim_time true
if [ -z "$ground_truth_pose_topic" ]; then
    roslaunch airsim_ros_wrapper airsim_node.launch --wait
else
    roslaunch airsim_ros_wrapper airsim_node.launch ground_truth_pose_topic:=$ground_truth_pose_topic --wait
fi