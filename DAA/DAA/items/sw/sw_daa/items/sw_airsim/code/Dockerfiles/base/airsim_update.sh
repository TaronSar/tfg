#!/usr/bin/env bash

# Navigate to the correct context directory for docker build
this_file_path () {
    local src=${BASH_SOURCE[0]}
    local path=

    while [ -L "$src" ]; do 
        path=$( cd -P "$( dirname "$src" )" >/dev/null 2>&1 && pwd )
        src=$(readlink "$src")
        [[ $src != /* ]] && src=$path/$src 
    done
    echo $( cd -P "$( dirname "$src" )" >/dev/null 2>&1 && pwd )
}

cd $(this_file_path)/../..

# Build updated airsim image with local AirSim source code
DOCKER_BUILDKIT=1 docker image build -t airsim:latest -f Dockerfiles/base/airsim_update.Dockerfile .