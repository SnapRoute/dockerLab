#!/bin/bash
source $(dirname "$0")/source.env

# configure tacacs
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX POST -d '{"ServerIp":"10.0.0.254","Secret":"SNAPROUTE","SourceIntf":"ma1"}' "$SWITCH1_SCHEMA://localhost:$SWITCH1_PORT/public/v1/config/Tacacs"
curl --insecure -u $SWITCH1_USERNAME:$SWITCH1_PASSWORD -sX PATCH -d '{"Enable":"true"}' "$SWITCH1_SCHEMA://localhost:$SWITCH1_PORT/public/v1/config/TacacsGlobal"

curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX POST -d '{"ServerIp":"10.0.0.254","Secret":"SNAPROUTE","SourceIntf":"ma1"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/Tacacs"
curl --insecure -u $SWITCH2_USERNAME:$SWITCH2_PASSWORD -sX PATCH -d '{"Enable":"true"}' "$SWITCH2_SCHEMA://localhost:$SWITCH2_PORT/public/v1/config/TacacsGlobal"

curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX POST -d '{"ServerIp":"10.0.0.254","Secret":"SNAPROUTE","SourceIntf":"ma1"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/Tacacs"
curl --insecure -u $SWITCH3_USERNAME:$SWITCH3_PASSWORD -sX PATCH -d '{"Enable":"true"}' "$SWITCH3_SCHEMA://localhost:$SWITCH3_PORT/public/v1/config/TacacsGlobal"


