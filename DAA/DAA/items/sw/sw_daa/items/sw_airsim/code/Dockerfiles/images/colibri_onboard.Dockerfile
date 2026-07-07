FROM catecupia/colibri_onboard_base:latest

COPY ./entrypoints/colibri_onboard/entrypoint_colibri_state_machine.sh /
COPY ./entrypoints/colibri_onboard/entrypoint_ual_px4.sh /
COPY ./entrypoints/colibri_onboard/entrypoint_ual_safety_pilot.sh /
COPY ./entrypoints/colibri_onboard/entrypoint_ual_teleop_key.sh /
COPY ./entrypoints/colibri_onboard/entrypoint_ual_record_waypoints.sh /
COPY ./entrypoints/colibri_onboard/entrypoint_ual_track_waypoints.sh /
COPY ./entrypoints/colibri_onboard/entrypoint_target_detector.sh /
COPY ./entrypoints/colibri_onboard/entrypoint_roscore.sh /
