#!/bin/sh

docker run -it --rm --log-driver=syslog --name test-instance -P $1
