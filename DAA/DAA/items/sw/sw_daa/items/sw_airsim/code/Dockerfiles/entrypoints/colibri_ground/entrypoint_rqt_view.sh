#!/bin/bash
set -e
source "/opt/ros/$ROS_DISTRO/setup.bash"

rosparam set use_sim_time true

roslaunch_file="/tmp/launch_simulator.launch"
echo "<?xml version=\"1.0\"?>" > $roslaunch_file
echo "<launch>" >> $roslaunch_file
echo "  <node pkg=\"rqt_image_view\" type=\"rqt_image_view\" name=\"rqt_image_view_1\" output=\"screen\" args=\"/airsim_node/PX4/camera_forward_d/DepthPerspective/image\" />" >> $roslaunch_file
echo "  <node pkg=\"rqt_image_view\" type=\"rqt_image_view\" name=\"rqt_image_view_2\" output=\"screen\" args=\"/airsim_node/PX4/camera_forward/Scene/image\" />" >> $roslaunch_file
echo "  <node pkg=\"rqt_image_view\" type=\"rqt_image_view\" name=\"rqt_image_view_3\" output=\"screen\" args=\"/airsim_node/PX4/camera_down/Scene/image\" />" >> $roslaunch_file
echo "  <node pkg=\"rqt_image_view\" type=\"rqt_image_view\" name=\"rqt_image_view_4\" output=\"screen\" args=\"/airsim_node/PX4/lidar_right/DepthPerspective/image\" />" >> $roslaunch_file
echo "  <node pkg=\"rqt_image_view\" type=\"rqt_image_view\" name=\"rqt_image_view_5\" output=\"screen\" args=\"/airsim_node/PX4/lidar_left/DepthPerspective/image\" />" >> $roslaunch_file
echo "</launch>" >> $roslaunch_file

# Launch the roslaunch file
roslaunch $roslaunch_file --wait
