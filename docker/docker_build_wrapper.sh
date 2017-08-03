#!/bin/bash
set -e

DOCKER_REPO=$1
shift
DOCKER_IMAGE_NAME=$1
shift
DOCKERFILE=$1
shift
TARGET_CONTEXT_DIRECTORIES=$@

BUILD_CONTEXT=/tmp/builder/$DOCKER_IMAGE_NAME

DOCKER_TARGET="$DOCKER_REPO:$DOCKER_IMAGE_NAME"

echo "Building $DOCKER_TARGET from $DOCKERFILE using $TARGET_CONTEXT_DIRECTORIES"
#docker rmi -f $DOCKER_TARGET
rm -rf $BUILD_CONTEXT && mkdir -p $BUILD_CONTEXT/context && cp $DOCKERFILE $BUILD_CONTEXT

function cleanup {
  rm -rf $BUILD_CONTEXT
}
trap cleanup EXIT

for folder in "${TARGET_CONTEXT_DIRECTORIES[@]}"; do
    cp -R $folder $BUILD_CONTEXT/context
done

docker build --rm -t $DOCKER_TARGET -f $BUILD_CONTEXT/$DOCKERFILE $BUILD_CONTEXT
