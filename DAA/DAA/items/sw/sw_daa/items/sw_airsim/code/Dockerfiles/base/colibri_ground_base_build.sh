#!/usr/bin/env bash

docker rmi -f colibri_ground_base

DOCKER_BUILDKIT=1 docker image build -t colibri_ground_base -f code/Dockerfiles/base/colibri_ground_base.Dockerfile .

docker image tag colibri_ground_base catecupia/colibri_ground_base:latest