#!/bin/bash

CONTAINER_EXISTS=$(docker container ls | grep colibri_ground)
if [ "$CONTAINER_EXISTS" ]
then
    docker container rm -f colibri_ground
fi

SETTINGS_DIR=${SETTINGS_DIR:-$(pwd)/settings}

# Create container
xhost +local: && \
docker container run -d --rm \
        --name colibri_ground \
        --gpus all \
        --privileged \
        --security-opt apparmor:unconfined \
        --ipc host \
        --network host \
        --env DISPLAY=$DISPLAY \
        --env NVIDIA_VISIBLE_DEVICES=all \
        --env NVIDIA_DRIVER_CAPABILITIES=all \
        --env QT_X11_NO_MITSHM=1 \
        --volume "$XAUTH:$XAUTH" \
        --volume "/tmp/.X11-unix:/tmp/.X11-unix":rw \
        --volume /etc/group:/etc/group:ro \
        --volume /etc/passwd:/etc/passwd:ro \
        --volume /etc/shadow:/etc/shadow:ro \
        --volume /etc/sudoers.d:/etc/sudoers.d:ro \
        --volume /etc/sudoers:/etc/sudoers:ro \
        --volume "$SETTINGS_DIR/algorithms/fleet_manager/config:/root/fleet_manager_ws/src/colibri_fleet_manager/config" \
        --volume "$SETTINGS_DIR/algorithms/fleet_manager/data:/root/fleet_manager_ws/src/colibri_fleet_manager/data" \
        --volume "$SETTINGS_DIR/algorithms/fleet_manager/rviz/planners.rviz/:/opt/ros/noetic/share/rviz/planners.rviz" \
        --volume "$SETTINGS_DIR/algorithms/fleet_manager/launch/planner.launch/:/opt/ros/noetic/share/heuristic_planners/launch/planner.launch" \
        --volume "$SETTINGS_DIR/algorithms/fleet_manager/resources/:/opt/ros/noetic/share/heuristic_planners/resources" \
        --volume "$SETTINGS_DIR/fleet.json:/root/fleet.json" \
        colibri_ground:latest tail -f /dev/null >/dev/null 2>&1