#!/bin/bash

CONTAINER_EXISTS=$(docker container ls | grep airsim)
if [ "$CONTAINER_EXISTS" ]
then
    docker container rm -f airsim
fi

uav_name=$1
world_name=$2
store_bbox=${3:-false}
airsim_vehicle_name=${4:-PX4}
airsim_camera_name=${5:-camera_forward}
airsim_camera_name_d=${6:-camera_forward_d}
SETTINGS_DIR=${SETTINGS_DIR:-$(pwd)/settings}
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
OUTPUT_DIR="$SCRIPT_DIR/../../items/sim/synthetic_data_${world_name}"

# Create container
xhost +local: && \
docker container run -d --rm \
        --name airsim \
        --gpus all \
        --security-opt apparmor:unconfined \
        --ipc host \
        --network host \
        --env="DISPLAY=$DISPLAY" \
        --env MAIN_UAV_NAME=$uav_name \
        --env WORLD_NAME=$world_name \
        --env STORE_BBOX=$store_bbox \
        --env AIRSIM_VEHICLE_NAME=$airsim_vehicle_name \
        --env AIRSIM_CAMERA_NAME=$airsim_camera_name \
        --env AIRSIM_CAMERA_NAME_D=$airsim_camera_name_d \
        --env QT_X11_NO_MITSHM=1 \
        --env XAUTHORITY=$XAUTH \
        --volume "$XAUTH:$XAUTH" \
        --volume "/tmp/.X11-unix:/tmp/.X11-unix" \
        --volume "$SETTINGS_DIR/algorithms/assets/dynamic.json:/root/settings/assets/dynamic.json" \
        --volume "$SETTINGS_DIR/algorithms/assets/static.json:/root/settings/assets/static.json" \
        --volume "$SETTINGS_DIR/algorithms/assets/dynamics_ids.json:/root/settings/assets/dynamics_ids.json" \
        --volume "$SETTINGS_DIR/fleet.json:/root/settings/fleet.json" \
        --volume "$SETTINGS_DIR/algorithms/assets/dummy_uavs.json:/root/settings/assets/dummy_uavs.json" \
        --volume "$SETTINGS_DIR/algorithms/assets/graphs/:/root/assets/graphs/" \
        --volume "$SETTINGS_DIR/trajectories/default.yaml:/root/settings/trajectories/default.yaml" \
        --volume "$SETTINGS_DIR/algorithms/airsim_wrapper/airsim_node.launch:/opt/ros/noetic/share/airsim_ros_wrapper/launch/airsim_node.launch" \
        --volume $(pwd)/Dockerfiles/entrypoints/airsim/entrypoint_assets_manager.sh:/entrypoint_assets_manager.sh \
        --volume $(pwd)/Dockerfiles/entrypoints/airsim/entrypoint_veronte_bridge.sh:/entrypoint_veronte_bridge.sh \
        --volume $(pwd)/Dockerfiles/entrypoints/airsim/airsim_simulation_runner.py:/root/airsim_simulation_runner.py \
        --volume $(pwd)/Dockerfiles/entrypoints/airsim/airsim_assets_manager.py:/root/airsim_assets_manager.py \
        --volume $(pwd)/Dockerfiles/entrypoints/airsim/entrypoint_bounding_box_simulator.sh:/entrypoint_bounding_box_simulator.sh \
        --volume $(pwd)/Dockerfiles/entrypoints/airsim/colors_table.json:/root/colors_table.json \
        --volume $(pwd)/Dockerfiles/entrypoints/airsim/segmentation_dataset_builder.py:/root/settings/segmentation_dataset_builder.py \
        --volume "$OUTPUT_DIR:/root/synthetic_data" \
	--volume /$HOME/DAA/:/workspace:rw \
        airsim:latest tail -f /dev/null >/dev/null 2>&1
