#!/bin/bash

CONTAINER_EXISTS=$(docker container ls | grep colibri_interface)
if [ "$CONTAINER_EXISTS" ]
then
    docker container rm -f colibri_interface
fi

SETTINGS_DIR=${SETTINGS_DIR:-$(pwd)/settings}

# Create container
xhost +local: && \
docker container run -d --rm \
        --name colibri_interface \
        --gpus all \
        --privileged \
        --security-opt apparmor:unconfined \
        --ipc host \
        --network host \
        --env SIMULATOR_WORLD_NAME=$1 \
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
        --volume "$SETTINGS_DIR/algorithms/interface/data/:/root/interface/" \
        --volume "$SETTINGS_DIR/algorithms/interface/gcs.launch/:/opt/ros/noetic/share/colibri_uav_interface/launch/gcs.launch" \
        --volume "$SETTINGS_DIR/fleet.json:/root/fleet.json" \
        colibri_interface:latest tail -f /dev/null >/dev/null 2>&1