#!/bin/bash
set -e

DOCKER_BUILD_WRAPPER=scripts/docker_build_wrapper.sh

$DOCKER_BUILD_WRAPPER snaproute/labs device_base device_base/Dockerfile device_base/context/
$DOCKER_BUILD_WRAPPER snaproute/labs client client/Dockerfile client/context/
$DOCKER_BUILD_WRAPPER snaproute/labs sysadmin sysadmin/Dockerfile sysadmin/context/
