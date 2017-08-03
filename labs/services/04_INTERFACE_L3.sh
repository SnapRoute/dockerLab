#!/bin/bash
source $(dirname "$0")/source.env

# configure L3 interfaces on switch1
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX POST -d '{"IntfRef":"vlan10", "AdminState":"UP", "IpAddr":"10.0.0.1/24"}' "$SWITCH1_SCHEMA://localhost:8001/public/v1/config/IPv4Intf"

curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX POST -d '{"IntfRef":"Loopback1", "AdminState":"UP", "IpAddr":"1.0.0.1/32"}' "$SWITCH1_SCHEMA://localhost:8001/public/v1/config/IPv4Intf"


# configure L3 interfaces on switch2
curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX POST -d '{"IntfRef":"vlan10", "AdminState":"UP", "IpAddr":"10.0.0.2/24"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/IPv4Intf"

curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX POST -d '{"IntfRef":"Loopback1", "AdminState":"UP", "IpAddr":"1.0.0.2/32"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/IPv4Intf"


# configure L3 interfaces on switch3
curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX POST -d '{"IntfRef":"vlan10", "AdminState":"UP", "IpAddr":"10.0.0.3/24"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/IPv4Intf"

curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX POST -d '{"IntfRef":"Loopback1", "AdminState":"UP", "IpAddr":"1.0.0.3/32"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/IPv4Intf"

