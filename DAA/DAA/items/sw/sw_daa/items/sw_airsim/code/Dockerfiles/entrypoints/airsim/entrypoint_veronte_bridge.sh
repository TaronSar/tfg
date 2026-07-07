#!/bin/bash
set -e

SCRIPT_DIR="/workspace/items/sw/sw_daa/items/_sw_perception/items/sw_gnssdenied/items/sw_rosws/"

echo "=========================================="
echo "AirSim-Veronte Bridge Launcher"
echo "=========================================="
echo ""

echo "[1/4] Changing to workspace directory..."
cd "$SCRIPT_DIR"
echo "Working directory: $(pwd)"
echo ""

echo "[2/4] Building ROS workspace with catkin_make..."
if catkin_make; then
    echo "catkin_make completed"
else
    echo "catkin_make failed, continuing to next step..."
fi
echo ""

echo "[3/4] Sourcing ROS environment..."
source /opt/ros/$ROS_DISTRO/setup.bash
source devel/setup.bash
echo "ROS environment sourced"
echo ""

echo "[4/4] Launching AirSim-Veronte Bridge..."
echo "=========================================="
rosrun veronte_sil airsim_veronte_bridge.py
