#!/usr/bin/env python
import argparse
import sys
import yaml
import rospy
import rospkg
import math
from uav_abstraction_layer.srv import TakeOff, GoToWaypoint, Land
from geometry_msgs.msg import PoseStamped
from loguru import logger

SYNC_START_PARAM = "/airsim/wp1_start_time"
OBJECTS_FINISHED_PARAM = "/airsim/objects_finished"
UAL_POSE_TOPIC = "/uav_0/ual/pose"
ORIENTATION_TOLERANCE = 0.5
POSITION_TOLERANCE = 1.5
CONVERGENCE_POLL_RATE_HZ = 20  # How often to check position+orientation convergence.


# _orientation_within_tolerance will check if the current orientation is within a certain tolerance
def _orientation_within_tolerance(current_q, target_q, tol):
    # q and -q represent the same rotation, so compare both signs.
    diffs_same_sign = [
        abs(current_q.x - target_q.x),
        abs(current_q.y - target_q.y),
        abs(current_q.z - target_q.z),
        abs(current_q.w - target_q.w),
    ]
    diffs_flipped_sign = [
        abs(current_q.x + target_q.x),
        abs(current_q.y + target_q.y),
        abs(current_q.z + target_q.z),
        abs(current_q.w + target_q.w),
    ]
    return max(diffs_same_sign) <= tol or max(diffs_flipped_sign) <= tol


# _position_within_tolerance will check if the current position is within a certain tolerance
def _position_within_tolerance(current_p, target_p, tol):
    diffs = [
        abs(current_p.x - target_p.x),
        abs(current_p.y - target_p.y),
        abs(current_p.z - target_p.z),
    ]
    return max(diffs) <= tol

# track_waypoints generates a waypoints route from default.yaml using ROS
def track_waypoints():
    # Parse arguments
    parser = argparse.ArgumentParser(description='Track waypoints defined in a yaml file')
    # plan_package is ROS packet where the plan is
    parser.add_argument('-plan_package', type=str, default='uav_abstraction_layer',
                        help='Name of the package where plan to track is stored')
    # plan_file is the plan file
    parser.add_argument('-plan_file', type=str, default='wp_default.yaml',
                        help='Name of the file inside plan_package/plans')
    # wait_for is the interactive wait mode
    parser.add_argument('-wait_for', type=str, default='none',
                        help='Wait for human response: [none]/[path]/[wp]')
    # auto_takeoff is the automatic takeoff option
    parser.add_argument('-auto_takeoff', type=bool, default=True,
                        help='Takeoff automatically before tracking waypoints')
    # auto_land is the automatic landing option
    parser.add_argument('-auto_land', type=bool, default=True,
                        help='Land automatically after tracking waypoints')

    args, unknown = parser.parse_known_args()
    # utils.check_unknown_args(unknown)

    # Initialize ROS node
    rospy.init_node('waypoint_tracker')

    # Clear previous sync value from older runs.
    if rospy.has_param(SYNC_START_PARAM):
        rospy.delete_param(SYNC_START_PARAM)

    file_name = args.plan_file
    # Autocomplete file extension
    if not file_name.endswith('.yaml'):
        file_name = file_name + '.yaml'

    if file_name.startswith('/'):
        file_url = file_name
    else:
        file_url = rospkg.RosPack().get_path(args.plan_package) + '/plans/' + file_name

    file_name = file_url.split('/')[-1]

    # Open yaml file
    with open(file_url, 'r') as wp_file:
        wp_data = yaml.safe_load(wp_file)

    # If frame_id is not specified, log error and exit
    if 'frame_id' not in wp_data:
        rospy.logerr("Must specify frame_id in waypoints file")  # TODO: default to ''?
        return

    # Waypoints list is built
    wp_list = []
    wp_times = []
    for wp_id in range(1000):
        if 'wp_' + str(wp_id) in wp_data:
            wp_raw = wp_data['wp_' + str(wp_id)]
            waypoint = PoseStamped()
            waypoint.header.frame_id = wp_data['frame_id']
            waypoint.pose.position.x =    wp_raw[0]
            waypoint.pose.position.y =    wp_raw[1]
            waypoint.pose.position.z =    wp_raw[2]
            waypoint.pose.orientation.x = wp_raw[3]
            waypoint.pose.orientation.y = wp_raw[4]
            waypoint.pose.orientation.z = wp_raw[5]
            waypoint.pose.orientation.w = wp_raw[6]
            wp_list.append(waypoint)
            # Store time field if present (index 7), otherwise None
            wp_times.append(wp_raw[7] if len(wp_raw) > 7 else None)

    # Waits for service disponibility
    go_to_waypoint_url = 'ual/go_to_waypoint'
    rospy.wait_for_service(go_to_waypoint_url)

    try:
        go_to_waypoint = rospy.ServiceProxy(go_to_waypoint_url, GoToWaypoint)

        # If takeoff is enabled, take off to the height of the first waypoint. If it fails, it keeps retrying until it succeeds.
        if args.auto_takeoff:
            take_off_url = 'ual/take_off'
            rospy.wait_for_service(take_off_url)
            take_off = rospy.ServiceProxy(take_off_url, TakeOff)
            logger.info("Taking off...")
            while not rospy.is_shutdown():
                try :
                    take_off(wp_list[0].pose.position.z , True)
                    break
                except rospy.ServiceException as e:
                    logger.error("Service call failed: %s", e)
                    logger.info("Retrying...")
                    rospy.sleep(1.0)

        # Track waypoints
        logger.info("Starting to track " + str(len(wp_list)) + " waypoints from " + file_name)
                
        # If wait_for is path or wp, it waits for user confirmation before starting to track waypoints or before going to each waypoint, respectively
        if args.wait_for == 'path' or args.wait_for == 'wp':
            answer = input("Continue? (y/N): ").lower().strip()
            if answer != 'y' and answer != 'yes':
                logger.info("Aborted")
                return

        # Iterates through waypoints using time field to schedule each one.
        # Timer starts when wp_1 is sent. Each waypoint is sent when elapsed time >= wp_time.
        
        # Send wp_0 immediately (it is also used for takeoff height, already handled above)
        go_to_waypoint(wp_list[0], True)
        logger.info("Sent wp_0")
        logger.info("Waiting to reach wp_1 and start synchronized timer...")
        go_to_waypoint(wp_list[1], True)

        # Start shared timer exactly when wp_1 has been reached.
        start_time = rospy.get_time()
        rospy.set_param(SYNC_START_PARAM, start_time)
        logger.info("Synchronized timer started at t={:.3f}".format(start_time))
        
        waypoint_index = 2  # Start from wp_2 since wp_0 and wp_1 are already sent
        while waypoint_index < len(wp_list) and not rospy.is_shutdown():
            waypoint = wp_list[waypoint_index]
            wp_time = wp_times[waypoint_index]
            
            # If no time field, send immediately
            if wp_time is None:
                go_to_waypoint(waypoint, False)

                # Wait until orientation and position converge before advancing to next waypoint.
                convergence_rate = rospy.Rate(CONVERGENCE_POLL_RATE_HZ)
                while not rospy.is_shutdown():
                    try:
                        current_pose = rospy.wait_for_message(UAL_POSE_TOPIC, PoseStamped, timeout=0.2)
                    except rospy.ROSException:
                        continue

                    if (
                        _orientation_within_tolerance(
                            current_pose.pose.orientation,
                            waypoint.pose.orientation,
                            ORIENTATION_TOLERANCE,
                        )
                        and _position_within_tolerance(
                            current_pose.pose.position,
                            waypoint.pose.position,
                            POSITION_TOLERANCE,
                        )
                    ):
                        break
                    convergence_rate.sleep()

                logger.info("Waypoint {} reached position+orientation (no time field). Moving to next.".format(waypoint_index))
                waypoint_index += 1
                continue

            # Wait until elapsed time >= wp_time, sleeping the remaining time each iteration
            while not rospy.is_shutdown():
                elapsed = rospy.get_time() - start_time
                remaining = wp_time - elapsed
                if remaining <= 0:
                    break
                rospy.sleep(remaining)
                logger.info("t={:.2f}s: Sending waypoint {} ({:.2f}, {:.2f}, {:.2f}, {:.2f}, {:.2f}, {:.2f}, {:.2f})".format(
                rospy.get_time() - start_time,
                waypoint_index,
                waypoint.pose.position.x,
                waypoint.pose.position.y,
                waypoint.pose.position.z,
                waypoint.pose.orientation.x,
                waypoint.pose.orientation.y,
                waypoint.pose.orientation.z,
                waypoint.pose.orientation.w,
            ))
            go_to_waypoint(waypoint, False)

            waypoint_index += 1

        # Landing
        # land_url = 'ual/land'
        # rospy.wait_for_service(land_url)
        # land = rospy.ServiceProxy(land_url, Land)
        # land(True) # Blocking - wait for landing to finish
        
        # Hold position and orientation at last waypoint indefinitely
        go_to_waypoint(waypoint, True)
        logger.info("All objects finished. Holding position and orientation...")
        
        # Wait for all dynamic objects to finish their paths
        logger.info("UAV finished waypoints. Waiting for dynamic objects to finish...")
        while not rospy.is_shutdown() and not rospy.get_param(OBJECTS_FINISHED_PARAM, False):
            rospy.sleep(0.5)

        
        rospy.spin()

        return
    

    except rospy.ServiceException as e:
        logger.error("Service call failed: %s", e)


if __name__ == "__main__":
    track_waypoints()

