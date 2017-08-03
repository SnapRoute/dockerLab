#!/bin/bash
source $(dirname "$0")/source.env

# configure dns
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX POST -d '{"IPAddr":"10.0.0.254"}' "$SWITCH1_SCHEMA://localhost:$SWITCH1_PORT/public/v1/config/DNSServer"
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX PATCH -d '{"Domain":"dockerlab.local"}' "$SWITCH1_SCHEMA://localhost:$SWITCH1_PORT/public/v1/config/DNSGlobal"

curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX POST -d '{"IPAddr":"10.0.0.254"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/DNSServer"
curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX PATCH -d '{"Domain":"dockerlab.local"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/DNSGlobal"

curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX POST -d '{"IPAddr":"10.0.0.254"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/DNSServer"
curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX PATCH -d '{"Domain":"dockerlab.local"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/DNSGlobal"
