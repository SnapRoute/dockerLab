#!/bin/bash
source $(dirname "$0")/source.env

# configure interfaces on switch1
echo "configuring switch1"
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX PATCH -d '{"IntfRef":"fpPort1", "Description":"switch2:port1", "AdminState":"UP"}' "$SWITCH1_SCHEMA://localhost:8001/public/v1/config/Port"
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX PATCH -d '{"IntfRef":"fpPort2", "Description":"switch3:port1", "AdminState":"UP"}' "$SWITCH1_SCHEMA://localhost:8001/public/v1/config/Port"

curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX POST -d '{"Name":"Loopback1"}' "$SWITCH1_SCHEMA://localhost:8001/public/v1/config/LogicalIntf"


# configure interfaces on switch2
echo "configuring switch2"
curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX PATCH -d '{"IntfRef":"fpPort1", "Description":"switch1:port1", "AdminState":"UP"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/Port"
curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX PATCH -d '{"IntfRef":"fpPort2", "Description":"client1:port1", "AdminState":"UP"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/Port"

curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX POST -d '{"Name":"Loopback1"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/LogicalIntf"


# configure interfaces on switch3
echo "configuring switch3"
curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX PATCH -d '{"IntfRef":"fpPort1", "Description":"switch1:port2", "AdminState":"UP"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/Port"
curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX PATCH -d '{"IntfRef":"fpPort2", "Description":"client2:port1", "AdminState":"UP"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/Port"

curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX POST -d '{"Name":"Loopback1"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/LogicalIntf"
