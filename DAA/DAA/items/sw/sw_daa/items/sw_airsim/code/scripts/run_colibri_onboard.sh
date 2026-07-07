#!/bin/bash

CONTAINER_EXISTS=$(docker container ls | grep colibri_onboard)
if [ "$CONTAINER_EXISTS" ]
then
    docker container rm -f colibri_onboard
fi

# Add as environment variable
trajectory_file=$1
uav_name=$2
SETTINGS_DIR=${SETTINGS_DIR:-$(pwd)/settings}

# Create container
xhost +local: && \
docker container run -d --rm \
        --name colibri_onboard \
        --gpus all \
        --security-opt apparmor:unconfined \
        --ipc host \
        --network host \
        --env="DISPLAY=$DISPLAY" \
        --env QT_X11_NO_MITSHM=1 \
        --env XAUTHORITY=$XAUTH \
        --volume "$XAUTH:$XAUTH" \
        --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
        --env UAL_TRAJECTORY_FILE=$trajectory_file \
        --env ROS_NAMESPACE=$uav_name \
        --volume "$SETTINGS_DIR/trajectories/:/root/trajectories/" \
        --volume "$SETTINGS_DIR/algorithms/aruco_ros_detector/launch/aruco_detector_node.launch/:/opt/ros/noetic/share/aruco_ros_detector/launch/aruco_detector_node.launch" \
        --volume "$HOME/DAA/items/sw/sw_daa/items/sw_airsim/code/Dockerfiles/entrypoints/colibri_onboard/track_waypoints.py:/opt/ros/noetic/lib/uav_abstraction_layer/track_waypoints.py" \
        colibri_onboard:latest tail -f /dev/null >/dev/null 2>&1