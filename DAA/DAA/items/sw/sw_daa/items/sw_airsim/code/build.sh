#!/usr/bin/env bash

# Ensuring this script is being run from the correct directory
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

# Building base images
bash $(this_file_path)/Dockerfiles/build_base_images.sh

# Building top level images
docker rmi -f airsim colibri_ground colibri_onboard px4_sitl simulator
cd $(this_file_path)/Dockerfiles
docker build -t airsim -f images/airsim.Dockerfile . && \
docker build -t colibri_ground -f images/colibri_ground.Dockerfile . && \
docker build -t colibri_onboard -f images/colibri_onboard.Dockerfile . && \
docker build -t colibri_interface -f images/colibri_interface.Dockerfile . && \
docker build -t px4_sitl -f images/px4_sitl.Dockerfile . && \
docker build -t simulator -f images/simulator.Dockerfile .