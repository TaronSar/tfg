#!/bin/bash

CONTAINER_EXISTS=$(docker container ls | grep simulator)
if [ "$CONTAINER_EXISTS" ]
then
    docker container rm -f simulator
fi

if ! [ $1 ]; then
    echo "This script needs one argument with the simulator world name to launch!"
    exit 1
fi

SETTINGS_DIR=${SETTINGS_DIR:-$(pwd)/settings}
TEMPLATE_ARUCO_DIR=$(pwd)/../items/sim_Template/sim/algorithms/assets/textures/aruco_markers_6x6
RECORDS_DIR=$(pwd)/records

if [ ! -d "$TEMPLATE_ARUCO_DIR" ]; then
    echo "Template ArUco folder not found: $TEMPLATE_ARUCO_DIR"
    exit 1
fi

# Create records directory if it doesn't exist
if [ ! -d "$RECORDS_DIR" ]; then
    mkdir -p "$RECORDS_DIR"
fi

# Create container
xhost +local: && \
docker container run -d --rm \
        --name simulator \
        --gpus all \
        --privileged \
        --security-opt apparmor:unconfined \
        --ipc host \
        --network host \
        --env SIMULATOR_WORLD_NAME=$1 \
        --env DISPLAY=unix$DISPLAY \
        --env NVIDIA_VISIBLE_DEVICES=all \
        --env NVIDIA_DRIVER_CAPABILITIES=all \
        --env QT_X11_NO_MITSHM=1 \
        --volume "$XAUTH:$XAUTH" \
        --env XAUTHORITY=$XAUTH \
        --volume "$XAUTH:$XAUTH" \
        --volume "/tmp/.X11-unix:/tmp/.X11-unix":rw \
        --volume $(pwd)/simulator:/home/catec/simulator \
        --volume "$RECORDS_DIR:/home/catec/records" \
        --volume "$SETTINGS_DIR/internal/shared/settings.json:/home/catec/Documents/AirSim/settings.json" \
        --volume "$SETTINGS_DIR/algorithms/assets/textures/:/home/catec/textures/" \
        --volume "$TEMPLATE_ARUCO_DIR/:/home/catec/textures/aruco_markers_6x6/" \
        --volume $(pwd)/Dockerfiles/entrypoints/simulator/entrypoint_simulator.sh:/entrypoint_simulator.sh \
        simulator tail -f /dev/null >/dev/null 2>&1