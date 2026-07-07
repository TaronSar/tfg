#!/usr/bin/env bash

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

# mkdir -p DockerSavedImages
# echo " > Saving airsim..."
# docker save airsim | gzip > DockerSavedImages/airsim.tar.gz
# echo " > Saving colibri_ground..."
# docker save colibri_ground | gzip > DockerSavedImages/colibri_ground.tar.gz
# echo " > Saving colibri_onboard..."
# docker save colibri_onboard | gzip > DockerSavedImages/colibri_onboard.tar.gz
# echo " > Saving px4_sitl..."
# docker save px4_sitl | gzip > DockerSavedImages/px4_sitl.tar.gz
# echo " > Saving simulator..."
# docker save simulator | gzip > DockerSavedImages/simulator.tar.gz
echo " > Saving colibri_interface..."
docker save colibri_interface | gzip > DockerSavedImages/colibri_interface.tar.gz