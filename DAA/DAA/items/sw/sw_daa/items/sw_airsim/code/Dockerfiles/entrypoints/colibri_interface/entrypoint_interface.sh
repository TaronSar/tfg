set -e
source "/opt/ros/$ROS_DISTRO/setup.bash"
rosparam set use_sim_time true

roslaunch colibri_uav_interface gcs.launch map_path:="/root/interface/${SIMULATOR_WORLD_NAME}.bt" --wait