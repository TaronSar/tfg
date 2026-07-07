#!/usr/bin/env bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Default values
scale="1.0"
target_json="$SCRIPT_DIR/../../items/sim/PX4_LondonWorld.json"
intruder="track_1"
drone="track_0"
trajectory_file="$HOME/DAA/items/sw/sw_trajectory_generator/examples/all_encounters.h5"

usage() {
    cat <<EOF
Usage:
  ./build_and_launch_trajectories.sh [--scale <val>] [--target_json <path>] [--intruder <id>] [--drone <id>] [--trajectory_file <path>]

Defaults:
  --scale           $scale
  --target_json     $target_json
  --intruder        $intruder
  --drone           $drone
  --trajectory_file $trajectory_file
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --scale)           scale="$2";           shift 2;;
        --target_json)     target_json="$2";     shift 2;;
        --intruder)        intruder="$2";        shift 2;;
        --drone)           drone="$2";           shift 2;;
        --trajectory_file) trajectory_file="$2"; shift 2;;
        -h|--help)         usage; exit 0;;
        *) echo "Unknown option: $1" >&2; usage; exit 1;;
    esac
done

simulation_name="$(basename "$target_json" .json)"
world_name="${simulation_name##*_}"

echo "Simulation: $simulation_name | World: $world_name"

python3 "$SCRIPT_DIR/build_trajectories.py" \
    --scale-xy "$scale" \
    --simulation-file "$target_json" \
    --track-id "$intruder" \
    --yaml-track-id "$drone" \
    "$trajectory_file"

"$SCRIPT_DIR/simulation_config.sh" apply "$simulation_name"

"$SCRIPT_DIR/../launch_px4.sh" -w "$world_name" --waypoints_control --bounding_box_simulation