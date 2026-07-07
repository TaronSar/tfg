FROM catecupia/colibri_ground_base:latest

COPY ./entrypoints/colibri_ground/entrypoint_fleet_manager.sh /
COPY ./entrypoints/colibri_ground/entrypoint_hpp.sh /
COPY ./entrypoints/colibri_ground/entrypoint_hpp_rviz.sh /
COPY ./entrypoints/colibri_ground/entrypoint_rqt_view.sh /
COPY ./entrypoints/colibri_ground/entrypoint_roscore.sh /
COPY ./entrypoints/colibri_ground/entrypoint_mission_manager.sh /
