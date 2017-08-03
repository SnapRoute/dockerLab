#!/bin/bash
set -e

./docker_build_wrapper.sh snaproute/dockerlab device_base Dockerfile.device_base device_base/
./docker_build_wrapper.sh snaproute/dockerlab client Dockerfile.client client/
./docker_build_wrapper.sh snaproute/dockerlab sysadmin Dockerfile.sysadmin sysadmin/
