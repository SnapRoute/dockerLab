#!/bin/bash
source $(dirname "$0")/source.env

# enable LLDP on all leaves
echo "enabling LLDP"
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX PATCH -d '{"Enable":true}' "$SWITCH1_SCHEMA://localhost:8001/public/v1/config/LLDPGlobal"
curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX PATCH -d '{"Enable":true}' "$SWITCH2_SCHEMA://localhost:8002/public/v1/config/LLDPGlobal"
curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX PATCH -d '{"Enable":true}' "$SWITCH3_SCHEMA://localhost:8003/public/v1/config/LLDPGlobal"


