#!/usr/bin/env bash

# Bash colors
# --------------------------------------------------------------
END='\033[0m'       	  # Text Reset
PURPLE='\033[95m'       # Purple
BOLD='\033[1m'          # Bold
ORANGE='\033[0;33m'     # Orange
BLUE='\033[0;34m'       # Blue
ITALICS='\033[3m'       # Italics
CYAN='\033[0;36m'       # Cyan
RED='\033[0;31m'        # Red
GREEN='\033[0;32m'      # Green

# Move into the right dir
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
cd $(this_file_path)

# Ensuring tmux is installed
if ! [ -x "$(command -v tmux)" ]; then
  echo 'Error: tmux is not installed.' >&2
  exit 1
fi

# Ensuring docker is installed
if ! [ -x "$(command -v docker)" ]; then
  echo 'Error: docker is not installed.' >&2
  exit 1
fi

# Load images from DockerSavedImages
echo -e "Loading images, this may take a while..."
echo -e " > [0/6] Loading ${BOLD}${BLUE}airsim${END}..."
docker load < DockerSavedImages/airsim.tar.gz
echo -e " > [${GREEN}1${END}/6] Successfully loaded!"
echo -e " > [1/6] Loading ${BOLD}${BLUE}simulator${END}..."
docker load < DockerSavedImages/simulator.tar.gz
echo -e " > [${GREEN}2${END}/6] Successfully loaded!"
echo -e " > [2/6] Loading ${BOLD}${BLUE}px4_sitl${END}..."
docker load < DockerSavedImages/px4_sitl.tar.gz
echo -e " > [${GREEN}3${END}/6] Successfully loaded!"
echo -e " > [3/6] Loading ${BOLD}${BLUE}colibri_ground${END}..."
docker load < DockerSavedImages/colibri_ground.tar.gz
echo -e " > [${GREEN}4${END}/6] Successfully loaded!"
echo -e " > [4/6] Loading ${BOLD}${BLUE}colibri_onboard${END}..."
docker load < DockerSavedImages/colibri_onboard.tar.gz
echo -e " > [${GREEN}5${END}/6] Successfully loaded!"
echo -e " > [5/6] Loading ${BOLD}${BLUE}colibri_interface${END}..."
docker load < DockerSavedImages/colibri_interface.tar.gz
echo -e " > [${GREEN}6${END}/6] Successfully loaded!"

echo -e "${BOLD}${GREEN}All images loaded successfully!${END}"