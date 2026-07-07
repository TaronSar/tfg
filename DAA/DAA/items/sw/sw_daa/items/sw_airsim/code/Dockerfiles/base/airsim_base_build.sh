#!/usr/bin/env bash

docker rmi -f airsim_base

DOCKER_BUILDKIT=1 docker image build -t airsim_base -f  code/Dockerfiles/base/airsim_base.Dockerfile .

docker image tag airsim_base catecupia/airsim_base:latest