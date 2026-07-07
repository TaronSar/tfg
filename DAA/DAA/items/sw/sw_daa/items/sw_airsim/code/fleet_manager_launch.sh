#!/usr/bin/env bash
# title		     :launch.sh
# description    :script to launch fleet trayectory planner stuff
# author 	     :jimurillo
# bash version   :5.0.17(1) - (tested)
#===========================================================================================

#====================================
# Default options
show_loading_panel="true"

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
MAIN_LOGO=$(cat settings/internal/main_logo.txt)

# Function to handle SIGINT signal (Ctrl+C)
# --------------------------------------------------------------
function handle_sigint {
    echo -e "\n${RED}*** Script interrupted by user ***${END}"

	kill_all_processes

    exit 1
}

trap handle_sigint SIGINT

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

	local command="sleep $time_delay; docker container exec -it $container bash /entrypoint_${process}.sh"

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
	echo "\n"

	end_container "colibri_ground"
	tmux kill-session -t $SESSION:0
	clear
	echo -e "${GREEN}*** [$SESSION session]: All processes successfully closed ***${END}"
}

#====================================
# Start

# Test we are in the correct directory
if [ ! -f "fleet_manager_launch.sh" ]; then
	echo "Please run this script from the directory where it is located"
	exit 1
fi

# Set Session Name
SESSION="FM"
SESSIONEXISTS=$(tmux list-sessions | grep $SESSION)
LOCAL_IP='127.0.0.1'

# Only create tmux session if it doesn't already exist
if [ "$SESSIONEXISTS" = "" ] ; then

	# Create docker containers
	clear
	echo -e "${MAIN_LOGO}"
	echo -e " > ${PURPLE} Starting docker containers... ${END}"
	start_container "colibri_ground" 

   	# Start New Session with our name
   	tmux new-session -d -s $SESSION

   	# Name first Pane and start bash
   	tmux rename-window -t 0 'Main'
   	tmux setw synchronize-panes on
	tmux set -g mouse on
   	tmux send-keys -t 'Main' "export ROS_MASTER_URI=http://$LOCAL_IP:11311" C-m
   	tmux send-keys -t 'Main' "export ROS_IP=$LOCAL_IP" C-m
   	tmux send-keys -t 'Main' "tput reset" C-m
   	tmux setw synchronize-panes off
   	tmux send-keys -t {session}:{window}.{pane}

	# Fleet Manager	
	start_process 8 'Main'.0 colibri_ground fleet_manager

	# Create a new window named 'Aux' and launch nodes there
    tmux new-window -t $SESSION:1 -n 'Aux'
   	tmux setw synchronize-panes on
	tmux set -g mouse on
   	tmux send-keys -t 'Main' "export ROS_MASTER_URI=http://$LOCAL_IP:11311" C-m
   	tmux send-keys -t 'Main' "export ROS_IP=$LOCAL_IP" C-m
   	tmux send-keys -t 'Main' "tput reset" C-m
   	tmux setw synchronize-panes off
	tsplit_mat 2 2	

   	tmux send-keys -t {session}:{window}.{pane}
	start_process 0 'Aux'.0 "colibri_ground" "roscore"
	start_process 8 'Aux'.1 "colibri_ground" "hpp"
	start_process 8 'Aux'.2 "colibri_ground" "hpp_rviz"

	# Show Loading Pane
	if [ "$show_loading_panel" = "true" ] ; then
		clear
		echo -e "${MAIN_LOGO}"

		# Progress bar 0 to 10 seconds
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
			sleep 0.20
		done

		sleep 1
		clear
	fi
fi

# Attach Session, on the Main window
tmux attach-session -t $SESSION:0
kill_all_processes
exit 0