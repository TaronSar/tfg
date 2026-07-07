#!/usr/bin/env bash
# title		     :launch.sh
# description    :script to launch all necessary debug terminals to launch the customized uav simulation
# author 	     :dtejero 
# bash version   :5.0.17(1) - (tested)
#===========================================================================================

#====================================
# Default options
main_uav_name="uav_0"
world_name=""
keyboard_control="false"
waypoints_control="false"
waypoints_file="default.yaml"
record_waypoints="false"
interface="false"
assets_simulation="false"
bounding_box_simulation="false"
store_bbox="false"
target_detector="false"
show_loading_panel="true"
state_machine="false"
colibri_digital_twin="false"
pose_source="gnss"
airsim_vehicle_name="PX4"
airsim_camera_name="camera_forward"
airsim_camera_name_d="camera_forward_d"

# Bash colors
# --------------------------------------------------------------
END='\033[0m'       	# Text Reset
PURPLE='\033[95m'       # Purple
BOLD='\033[1m'          # Bold
ORANGE='\033[0;33m'     # Orange
BLUE='\033[0;34m'       # Blue
ITALICS='\033[3m'       # Italics
CYAN='\033[0;36m'       # Cyan
RED='\033[0;31m'        # Red
GREEN='\033[0;32m'      # Green
SETTINGS_DIR=""
MAIN_LOGO=""

# Function to print usage
# --------------------------------------------------------------
print_usage () { 
	echo -e "                                                                         
${PURPLE}--------------------------------------------------------------------------------------------------------------------------
----------------------------------------------------- ${BOLD}OPTIONS${END}${PURPLE} ------------------------------------------------------------
--------------------------------------------------------------------------------------------------------------------------${END}\n
--${BOLD}help${END}              | ${BOLD}-h${END}   ${ITALICS}flag to display options                ${END}\n
--${BOLD}waypoints_file${END}    | ${BOLD}-f${END}   ${ITALICS}waypoints file to track                ${END}   [ ${ORANGE}default:${END} default.yaml   ]  opt:${END} <${BLUE}str${END}>\n
--${BOLD}world_name${END}        | ${BOLD}-w${END}   ${ITALICS}world name inside simulator folder     ${END}   [ ${ORANGE}default:${END} <empty>        ]  opt:${END} <${BLUE}str${END}>\n
--${BOLD}sim${END}               | ${BOLD}-s${END}   ${ITALICS}settings folder name in ../items/      ${END}   [ ${ORANGE}default:${END} <empty>        ]  opt:${END} <${BLUE}str${END}>\n
--${BOLD}pose_source${END}       | ${BOLD}-p${END}   ${ITALICS}Autopilot pose source                  ${END}   [ ${ORANGE}default:${END} gnss           ]  opt:${END} <${BLUE}ext${END}, ${BLUE}gnss${END}, ${BLUE}gt${END}>\n
--${BOLD}airsim_vehicle_name${END}       ${ITALICS}AirSim vehicle name for captures        ${END}[ ${ORANGE}default:${END} PX4            ]  opt:${END} <${BLUE}str${END}>\n
--${BOLD}airsim_camera_name${END}        ${ITALICS}AirSim RGB/segmentation camera name     ${END}[ ${ORANGE}default:${END} camera_forward ]  opt:${END} <${BLUE}str${END}>\n
--${BOLD}airsim_camera_name_d${END}      ${ITALICS}AirSim depth camera name                ${END}[ ${ORANGE}default:${END} camera_forward_d ]  opt:${END} <${BLUE}str${END}>\n
--${BOLD}interface${END}                ${ITALICS}flag to launch colibri interface          ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}keyboard_control${END}         ${ITALICS}flag to enable keyboard control           ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}waypoints_control${END}        ${ITALICS}flag to enable waypoints tracking by file ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}record_waypoints${END}         ${ITALICS}flag to launch a helper to record wp      ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}assets_simulation${END}        ${ITALICS}flag to run assets simulation             ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}bounding_box_simulation${END}  ${ITALICS}flag to publish moving-object 3D bboxes  ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}store_bbox${END}               ${ITALICS}flag to save RGB images with bbox drawn    ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}target_detector${END}          ${ITALICS}flag to run an aruco detector node        ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}state_machine${END}            ${ITALICS}flag to run the COLIBRI state machine     ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}test_all${END}                 ${ITALICS}flag to run all the previous flags        ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>\n
--${BOLD}colibri_digital_twin${END}     ${ITALICS}automatic enable for COLIBRI digital twin ${END}[ ${ORANGE}default:${END} false          ]  <${BLUE}flag${END}>
    [*] --world_name        [ AerotecnicPlant ] ${ITALICS}(if no other world name option was specified) ${END}
    [*] --interface         [ true ]${END}
    [*] --state_machine     [ true ]${END}
    [*] --pose_source       [ gt ]${END}
    [*] --assets_simulation [ true ]${END}

\nPlease, configure properly the following files before running the script (default config is provided): \n
* ${BOLD}settings/sensors.json${END}  
  -> ${ITALICS} Onboard Sensors${END} 
* ${BOLD}settings/config_simulation.json${END}  
  -> ${ITALICS} Simulation parameters (clock speed, gnss origin, etc)${END} 
* ${BOLD}settings/algorithms/assets/dynamic.json${END}  
  -> ${ITALICS} Include here dynamic assets instances (used in --assets_simulation mode)${END}
* ${BOLD}settings/algorithms/assets/static.json${END}  
  -> ${ITALICS} Include here static assets instances (used in --assets_simulation mode)${END}
* ${BOLD}settings/fleet.json${END}  
  -> ${ITALICS} Include here fleet waypoints to simulate UAV swarm (used in --assets_simulation mode)${END}
* ${BOLD}settings/algorithms/assets/textures/${END}  
  -> ${ITALICS} Include here textures png images (used in dynamic.json file)${END}
* ${BOLD}settings/algorithms/assets/dummy_uavs.json${END}  
  -> ${ITALICS} Include here configuration for simulating UAVs${END}
* ${BOLD}settings/trajectories/${END}  
  -> ${ITALICS} Include your waypoints files here following the format of the default.yaml file${END}
* ${BOLD}settings/internal/params_px4_gnss.json${END}  
  -> ${ITALICS} PX4 autopilot internal parameters (--pose_source: gnss)  ${END}
* ${BOLD}settings/internal/params_px4_ext.json${END}  
  -> ${ITALICS} PX4 autopilot internal parameters (--pose_source: ext; gt) ${END}

\n${PURPLE}--------------------------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------------------------
--------------------------------------------------------------------------------------------------------------------------${END}\n"

exit 0
}

# Function to handle SIGINT signal (Ctrl+C)
# --------------------------------------------------------------
function handle_sigint {
    echo -e "\n${RED}*** Script interrupted by user ***${END}"
    
    # Kill any lingering gnome-terminal pop-up windows
    pkill -f "gnome-terminal.*Pop-up" 2>/dev/null || true

	kill_all_processes

    exit 1
}

trap handle_sigint SIGINT

# Function to evaluate bash arguments
# --------------------------------------------------------------
eval_options()
{
	while test $# -gt 0
	do
		case "$1" in

		-h|--help)
			print_usage;
			exit 0
      		shift;;

		-w|--world_name)
			export world_name="$2";
			shift 2;;

		-f|--waypoints_file)
			export waypoints_file="$2";
			shift 2;;

		-p|--pose_source)
			export pose_source="$2";
			shift 2;;

		--airsim_vehicle_name)
			export airsim_vehicle_name="$2";
			shift 2;;

		--airsim_camera_name)
			export airsim_camera_name="$2";
			shift 2;;

		--airsim_camera_name_d)
			export airsim_camera_name_d="$2";
			shift 2;;

		--waypoints_control)
			export waypoints_control="true";
			shift;;
		
		--keyboard_control)
			export keyboard_control="true";
			shift;;

		--record_waypoints)
			export record_waypoints="true";
			shift;;

		--interface)
			export interface="true";
			shift;;
		
		--assets_simulation)
			export assets_simulation="true";
			shift;;

		--bounding_box_simulation)
			export bounding_box_simulation="true";
			export assets_simulation="true";
			shift;;

		--store_bbox)
			export store_bbox="true";
			export bounding_box_simulation="true";
			export assets_simulation="true";
			shift;;

		--target_detector)
			export target_detector="true";
			shift;;

		--state_machine)
			export state_machine="true";
			shift;;

		--colibri_digital_twin)
			export colibri_digital_twin="true";
			shift;;

		--test_all)
			export waypoints_control="true";
			export keyboard_control="true";
			export record_waypoints="true";
			export interface="true";
			export assets_simulation="true";
			export bounding_box_simulation="true";
			export store_bbox="true";
			export target_detector="true";
			export state_machine="true";
			export colibri_digital_twin="true";
			shift;;
			
		*)
		printf "Unknown option %s\n" "$1"
		exit 1;;
		esac
	done
}

# Function to start an specific docker container
# Usage: start_container <container_name> <optional: script_args>
# --------------------------------------------------------------
start_container()
{
	local container_name=$1
	local script_args=$2
	local script_path="./scripts/run_$container_name.sh"
	
	local container_exists=$(docker ps -a | grep $container_name)
	if [ "$container_exists" ] ; then
		echo -e "  >>> ${ORANGE}${BOLD}$container_name${END}${ORANGE} container already exists, removing... ${END}"
		docker container rm -f $container_name >/dev/null
		start_container $container_name $script_args
	else
		echo -e "  >>> Starting ${BLUE}${BOLD}$container_name${END} container"
		$script_path $script_args
		local container_exists=$(docker ps -a | grep $container_name)
		if [ ! "$container_exists" ] ; then
			echo -e "  >>>$RED $container_name container could not be started $END"
			exit 1
		fi
	fi
}

# Function to stop an specific docker container
# Usage: end_container <container_name>
# --------------------------------------------------------------
end_container()
{
	local container_name=$1
	local container_exists=$(docker ps -a | grep $container_name)
	if [ "$container_exists" ] ; then
		echo -e "  >>> Stopping ${BLUE}${BOLD}$container_name${END} container"
		docker container rm -f $container_name >/dev/null
	fi

}

# Function to start a process in a tmux pane or in a pop-up terminal
# Usage: start_process <time_delay> <tmux_window.tmux_pane> <container> <process>
# Note: If tmux_window.tmux_pane is "pop-up", the process will be started in a new gnome terminal
# --------------------------------------------------------------
start_process()
{
	local time_delay=$1
	local tmux_pane=$2
	local container=$3
	local process=$4
	local arguments=$5

	local command="sleep $time_delay; docker container exec -it $container bash /entrypoint_${process}.sh $arguments"

	if [ "$tmux_pane" = "pop-up" ] ; then
		gnome-terminal --tab --title="Pop-up: $process " -- bash -c "$command"
	else
		tmux send-keys -t $SESSION:$tmux_pane "$command" C-m
	fi
}

# Function to kill all processes and close the tmux session
# --------------------------------------------------------------
kill_all_processes()
{
	tmux setw synchronize-panes on
	tmux send-keys -t $SESSION:0 C-c
	tmux send-keys -t $SESSION:0 C-c
	tmux send-keys -t $SESSION:0 C-c
	tmux setw synchronize-panes off

	clear
	echo -e "${MAIN_LOGO}"
	echo "Waiting for processes to close (5s)"
	for i in {1..5}
	do
		sleep 1
		echo -n "."
	done
	echo " "

	end_container "airsim"
	end_container "colibri_ground"
	end_container "colibri_onboard"
	end_container "px4_sitl"
	end_container "simulator"
	
	if [ "$interface" = "true" ] ; then
		end_container "colibri_interface"
	fi

	tmux kill-session -t $SESSION:0
	clear
	echo -e "${GREEN}*** [$SESSION session]: All processes successfully closed ***${END}"
}

# Return a string with the path of the currently running file
# --------------------------------------------------------------
this_file_path () {
    local src=${BASH_SOURCE[0]}
    local path=

    # bulletproof: resolve $src until the file is no longer a symlink
    while [ -L "$src" ]; do 
        path=$( cd -P "$( dirname "$src" )" >/dev/null 2>&1 && pwd )
        src=$(readlink "$src")
        [[ $src != /* ]] && src=$path/$src 
    done
    echo $( cd -P "$( dirname "$src" )" >/dev/null 2>&1 && pwd )
}

# Protect against user-level .tmux.conf. 
# Allow custom config via environment variable SIM_TMUX_CONF
# --------------------------------------------------------------
tmux_no_conf()
{
    local tmux_binary=$(which tmux)

    if [ -z "$SIM_TMUX_CONF" ]
    then
        $tmux_binary -f /dev/null $@
    else
        $tmux_binary -f "$SIM_TMUX_CONF" $@
    fi
}

# Function to split tmux terminal into n x m matrix of panes
# --------------------------------------------------------------
tsplit_mat()
{
	local vert=$2
	local hori=$1
	for i in $(eval echo {1..$hori})
	do
		if [ "$i" -le 1 ]
		then
				continue
		fi

		tmux split-window -v
	done
	tmux select-layout even-vertical
	for k in $(eval echo {1..$hori})
	do
		for j in $(eval echo {1..$vert})
		do
		 	# echo $k $j
			if [ "$j" -le 1 ]
			then
					continue
			fi
			tmux split-window -h
			tmux select-pane -L
		done
		tmux select-pane -U
	done
}

#====================================
# Start

# Move into the proper directory for relative links to work
LAUNCH_DIR="$(this_file_path)"
cd "$LAUNCH_DIR"

eval_options "$@"


SETTINGS_DIR="$LAUNCH_DIR/settings"

if [ ! -d "$SETTINGS_DIR" ]; then
	echo "Settings directory not found: $SETTINGS_DIR"
	exit 1
fi

if [ ! -f "$SETTINGS_DIR/internal/main_logo.txt" ]; then
	echo "Cannot locate \"$SETTINGS_DIR/internal/main_logo.txt\"."
	exit 1
fi

export SETTINGS_DIR
MAIN_LOGO=$(cat "$SETTINGS_DIR/internal/main_logo.txt")

if [ "$colibri_digital_twin" = "true" ] ; then
	export assets_simulation="true";
	export interface="true";
	export state_machine="true";
	export pose_source="gt";
	if [ -z "$world_name" ]; then
		export world_name="AerotecnicPlant";
	fi
fi

# Check if simulator world file exists
if [ ! -f "./simulator/$world_name/LinuxNoEditor/$world_name.sh" ]; then
	echo "Selected world \"$world_name\" does not exist in simulator folder. 
Cannot locate \"simulator/$world_name/LinuxNoEditor/$world_name.sh\"."
	exit 1
fi

export setup_pose_source=$pose_source

if [ "$setup_pose_source" = "gt" ]; then
	export setup_pose_source="ext"
fi

# Create custom settings.json
if [ "$setup_pose_source" != "ext" ] && [ "$setup_pose_source" != "gnss" ]; then
	echo "Invalid pose_source. Please, use 'ext' or 'gnss' or 'gt'."
	exit 1
fi
"$SETTINGS_DIR/internal/setup.py" px4 $setup_pose_source

# Set Session Name
SESSION="COLIBRI"
SESSIONEXISTS=$(tmux list-sessions | grep $SESSION)
LOCAL_IP='127.0.0.1'


# Only create tmux session if it doesn't already exist
if [ "$SESSIONEXISTS" = "" ] ; then

	# Create docker containers
	clear
	echo -e "${MAIN_LOGO}"
	echo -e " > ${PURPLE} Starting docker containers... ${END}"
	start_container "airsim" "$main_uav_name $world_name $store_bbox $airsim_vehicle_name $airsim_camera_name $airsim_camera_name_d"
	start_container "colibri_ground" 
	start_container "colibri_onboard" "$waypoints_file $main_uav_name"
	start_container "px4_sitl" 
	start_container "simulator" $world_name

	if [ "$interface" = "true" ] ; then
		start_container "colibri_interface" $world_name
	fi

   	# Start New Session with our name
	tmux -f "$SETTINGS_DIR/internal/tmux.conf" new-session -d -s $SESSION 
   	tmux rename-window -t 0 'Main'
	tsplit_mat 2 6
	tmux setw synchronize-panes on
   	tmux send-keys -t 'Main' "export ROS_MASTER_URI=http://$LOCAL_IP:11311" C-m
   	tmux send-keys -t 'Main' "export ROS_IP=$LOCAL_IP" C-m
   	tmux send-keys -t 'Main' "tput reset" C-m
   	tmux setw synchronize-panes off

	# For interface window
	if [ "$interface" = "true" ] ; then
		tmux new-window -t $SESSION:1 -n 'Interface'
		tmux send-keys -t 'Interface' "export ROS_MASTER_URI=http://$LOCAL_IP:11311" C-m
		tmux send-keys -t 'Interface' "export ROS_IP=$LOCAL_IP" C-m
		tmux send-keys -t 'Interface' "tput reset" C-m
	fi

	start_process 0  'Main'.0  "airsim"           "roscore"
	start_process 0  'Main'.4  "simulator"        "simulator"
	start_process 0  'Main'.5  "px4_sitl"         "px4_sitl"
	start_process 8  'Main'.1  "airsim"           "airsim_wrapper" "/uav_0/mavros/vision_pose/pose"
	start_process 10 'Main'.2  "colibri_onboard"  "ual_px4"
	start_process 15 'Main'.6  "colibri_onboard"  "ual_safety_pilot"
   	
	if [ "$interface" = "true" ] ; then
		start_process 9 'Interface'  "colibri_interface"  "interface"
	fi
	
	if [ "$assets_simulation" = "true" ] ; then
		start_process 15 'Main'.7  "airsim"         "assets_manager"
		start_process 15 'Main'.8  "airsim"         "fleet_simulator"
	fi

	if [ "$target_detector" = "true" ] ; then
		start_process 15 'Main'.9  "colibri_onboard"  "target_detector"
	fi
	if [ "$keyboard_control" = "true" ] ; then
		start_process 15 "pop-up" "colibri_onboard"  "ual_teleop_key"
	fi
	if [ "$waypoints_control" = "true" ] ; then
		start_process 13 'Main'.3 "colibri_onboard"  "ual_track_waypoints"
	fi
	if [ "$record_waypoints" = "true" ] ; then
		start_process 15 "pop-up" "colibri_onboard"  "ual_record_waypoints"
	fi
	if [ "$state_machine" = "true" ] ; then
		start_process 15 'Main'.10 "colibri_onboard"  "colibri_state_machine"
		start_process 15 'Main'.11 "colibri_ground"   "mission_manager"
	fi
	if [ "$bounding_box_simulation" = "true" ] ; then
		start_process 30 "pop-up" "airsim"         "bounding_box_simulator"
	fi

	# Show Loading Pane
	if [ "$show_loading_panel" = "true" ] ; then
		clear
		echo -e "${MAIN_LOGO}"

		# Progress bar 0 to 15 seconds
		for i in {1..50}
		do
			# show a bar with # and the percentage
			echo -ne "${BOLD}                    ["
			for j in {1..50}
			do
				if [ "$j" -le "$i" ] ; then
					echo -ne "#"
				else
					echo -ne " "
				fi
			done
			echo -ne "] $((i*2))%\r${END}"
			sleep 0.30
		done

		sleep 1
		clear
	fi
fi

# Attach Session, on the Main window
tmux attach-session -t $SESSION:0

# When detach - Try to kill all processes
kill_all_processes
exit 0