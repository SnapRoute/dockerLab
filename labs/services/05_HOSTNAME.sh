#!/bin/bash
source $(dirname "$0")/source.env

# configure hostname
echo "configuring hostnames"
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX PATCH -d '{"Hostname":"service-switch1"}' "$SWITCH1_SCHEMA://localhost:$SWITCH1_PORT/public/v1/config/SystemParam"

curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX PATCH -d '{"Hostname":"service-switch2"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/SystemParam"

curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX PATCH -d '{"Hostname":"service-switch3"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/SystemParam"


