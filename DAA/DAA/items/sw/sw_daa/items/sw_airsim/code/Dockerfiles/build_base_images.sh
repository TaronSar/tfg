#!/usr/bin/env bash
# General launcher for building base images

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

cd $(this_file_path)/../..
code/Dockerfiles/base/colibri_onboard_base_build.sh --full
code/Dockerfiles/base/airsim_base_build.sh
code/Dockerfiles/base/colibri_ground_base_build.sh
code/Dockerfiles/base/colibri_interface_base_build.sh
code/Dockerfiles/base/simulator_base_build.sh