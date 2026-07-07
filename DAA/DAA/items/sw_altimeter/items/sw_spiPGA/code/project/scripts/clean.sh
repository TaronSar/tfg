#!/bin/bash

PRJ_DIR=$(pwd)/../..

rm -rf .Xil
rm -rf ../cmake/build

rm -rf ${PRJ_DIR}/platform
rm -rf ${PRJ_DIR}/.metadata
rm  ${PRJ_DIR}/.analytics
rm  ${PRJ_DIR}/*.log