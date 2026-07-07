#!/usr/bin/env bash
set -e

echo "Creating Python virtual environment..."
python3 -m venv .venv

echo "Activating virtual environment..."
source .venv/bin/activate

echo "Installing dependencies..."
pip install -r requirements.txt
pip install --no-deps sw_trajectory_generator/package/cam_track_gen-0.1.0-py3-none-any.whl

echo "Installing project (editable) for the daa_* packages..."
pip install -e . --no-deps

echo ""
echo "Virtual environment ready. Activate it with:"
echo "  source .venv/bin/activate"
