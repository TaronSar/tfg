#!/usr/bin/env bash

# if --full is passed, will use the full version of colibri onboard 
filename='colibri_onboard_base'
if [ "$1" == "--full" ]; then
    filename='colibri_onboard_base_full'    
fi

docker rmi -f colibri_onboard_base

DOCKER_BUILDKIT=1 docker image build -t colibri_onboard_base -f code/Dockerfiles/base/${filename}.Dockerfile .

docker image tag colibri_onboard_base catecupia/colibri_onboard_base:latest