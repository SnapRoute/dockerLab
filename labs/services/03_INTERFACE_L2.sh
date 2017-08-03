#!/bin/bash
source $(dirname "$0")/source.env

# configure vlans on switch1
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX POST -d '{"VlanId":10, "UntagIntfList":["fpPort1","fpPort2","fpPort3"]}' "$SWITCH1_SCHEMA://localhost:8001/public/v1/config/Vlan"


# configure vlans on switch2
curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX POST -d '{"VlanId":10, "UntagIntfList":["fpPort1","fpPort2"]}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/Vlan"


# configure vlans on switch3
curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX POST -d '{"VlanId":10, "UntagIntfList":["fpPort1","fpPort2"]}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/Vlan"
