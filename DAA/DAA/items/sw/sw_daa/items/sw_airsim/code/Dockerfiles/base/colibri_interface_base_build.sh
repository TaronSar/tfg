#!/usr/bin/env bash

docker rmi -f colibri_interface_base

DOCKER_BUILDKIT=1 docker image build -t colibri_interface_base -f code/Dockerfiles/base/colibri_interface_base.Dockerfile .

docker image tag colibri_interface_base catecupia/colibri_interface_base:latest