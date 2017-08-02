#!/bin/bash
source $(dirname "$0")/source.env

# configure dns
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX PATCH -d '{"Timezone":"America/New_York"}' "$SWITCH1_SCHEMA://localhost:$SWITCH1_PORT/public/v1/config/SystemParam"

curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX PATCH -d '{"Timezone":"America/Chicago"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/SystemParam"

curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX PATCH -d '{"Timezone":"America/Los_Angeles"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/SystemParam"

