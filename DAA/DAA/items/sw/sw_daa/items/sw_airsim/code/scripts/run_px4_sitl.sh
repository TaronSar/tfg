#!/bin/bash

CONTAINER_EXISTS=$(docker container ls | grep px4_sitl)
if [ "$CONTAINER_EXISTS" ]
then
    docker container rm -f px4_sitl
fi

# Create container
xhost +local: && \
docker container run -d --rm \
        --name px4_sitl \
        --gpus all \
        --security-opt apparmor:unconfined \
        --ipc host \
        --network host \
        --env="DISPLAY=$DISPLAY" \
        --env QT_X11_NO_MITSHM=1 \
        --env XAUTHORITY=$XAUTH \
        --volume "$XAUTH:$XAUTH" \
        --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
        px4_sitl:latest tail -f /dev/null >/dev/null 2>&1