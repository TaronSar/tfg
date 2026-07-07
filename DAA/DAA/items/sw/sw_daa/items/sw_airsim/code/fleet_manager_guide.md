# FLEET MANAGER

First, follow the instructions contained in README to setup the images.

## Configuring fleet manager

The main setup json file is [mission.json](settings/fleet_manager/config/mission.json).

There are two differents fields for each node in this file:

- **fleet_manager**: this node is in charge of computing the necessary obstacle avoidance trajectories given the initial positions of the drones and the target points (waypoints).
    - *objective-points*: waypoints ([x, y, z]).
    - *drone-depots*: initial position of drones ([x, y, z]).
    - *battery-clustering*: *true* if you want to take battery level into account when clustering. If not, *false*.
    - *battery-level*: array of battery level for each drone ([b0, b1, b2..., bn]).

- **planner_4d**: this node is responsible for calculating potential route conflicts and computing take-off delays to avoid them.
    - *priority_order*: array that defines the priority of each drone in order to solve conflicts. The drone id placed in first index is the one with the highest priority.
    - *security_distance*: the minimum distance at which conflict is considered to exist.
    - *min_time_gap*: minimum time gap that we need to achieve in case two trajectories are below the minimum distance.
    - *v_max*: drone cruising speed at which the trajectory time is calculated.
    - *acc*: drone acceleration.

For area covering node, we have another json file, [area_covering.json](settings/fleet_manager/config/area_covering.json).

- **area_covering**: this node calculates a list of waypoints with which it covers a given area. The node subscripts to a topic of occupancy grid map, a 2D map that is published by heuristic planners node. The desired height must be configured in [Configuring heuristic planners](#configuring-heuristic-planners).
    - *waypoint_radius*: minimum distance between waypoints.
    - *desired_area*: defines the dimensions and position of rectangle that will be covered - [x min, x max, y min, y max].
    - *max_prob*: maximum occupancy probability that is accepted as a valid region.

## Configuring heuristic planners

The launch file is [planner.launch](settings/fleet_manager/launch/planner.launch).

Most important parameters:
    - *map_name*: filename of the desired octomap (.bt).
    - *world_size*: x, y, z size needed to load the map.
    - *inflation_size*: size at which objects are inflated to ensure a safety distance.
    - *grid_slice_height*: height of the occupancy grid that is published to perform the area covering.

In case you want to change the map, add the .bt file to [resources](settings/fleet_manager/resources/3dmaps).

## Running fleet manager

To execute the fleet manager, you have to run the following script:

```
    ./fleet_manager_launch.sh 
```

Once the execution script has been executed, a tmux will open with two windows:

**"Main" window**: here is where we are going to execute the fleet manager nodes.

Before launch this nodes, we must wait until the aux nodes are up and running (the map will show up in rviz window).

First, we need to launch the **area_covering** node to obtain a valid list of waypoints.

        roslaunch colibri_fleet_manager area_covering.launch

Then, we must copy the [output points](settings/fleet_manager/data/objective_points.json) in [mission.json](settings/fleet_manager/config/mission.json), and if necessary add other single waypoints that we want to visit.

In order to compute the trayectory, we launch the **fleet_manager** node:

        roslaunch colibri_fleet_manager colibri_fleet_manager.launch

It will take about 3 or 4 minutes and the results will be displayed in some graphs while the algorithm is running.

To check the obtained route in rviz:

        rosrun colibri_fleet_manager show_paths.py

Finally, we need to obtain the final [json](settings/fleet_manager/data/routes_with_time.json) that will be used by simulator, with each drone take-off time. We launch the **planner_4d** node:

        roslaunch colibri_fleet_manager planner_4d.launch




**"Aux" window**: in this window, auxiliary nodes are executed, like roscore, rviz (visualization), and heuristic path planners (node that compute trayectory between two points).

### Compiling from source
Alternativally, you can compile the docker images from source. To do so, you have to run the following script to compile the base images:

```
    cd Dockerfiles/base
    ./build_base_files.sh
```
After that, you can compile the top level images with the modificable entrypoint:

```
    ./build_images.sh
```

After that, you can launch the simulator in the exact same way. 

You can also save the compiled version of the images with the following script:

```
    ./save_images.sh
```

Note: in the parent directory of this package must be located all the source code dependencies as: airsim, airsim_ros_wrapper, grvc-ual, heuristic path planners and colibri_fleet_manager.