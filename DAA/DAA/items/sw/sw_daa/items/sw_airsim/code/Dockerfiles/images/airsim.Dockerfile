FROM catecupia/airsim_base:latest

COPY ./entrypoints/airsim/entrypoint_airsim_wrapper.sh /
COPY ./entrypoints/airsim/entrypoint_assets_manager.sh /
COPY ./entrypoints/airsim/entrypoint_fleet_simulator.sh /
COPY ./entrypoints/airsim/entrypoint_roscore.sh /