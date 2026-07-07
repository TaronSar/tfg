#!/usr/bin/env bash

docker rmi -f simulator_base

DOCKER_BUILDKIT=1 docker image build -t simulator_base -f code/Dockerfiles/base/simulator_base.Dockerfile .

docker image tag simulator_base catecupia/simulator_base:latest
