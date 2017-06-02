#!/bin/bash
# stage scripts execute command outside of container instance on custom port

# enable LLDP on leaf1
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8001/public/v1/config/LLDPGlobal'

# enable LLDP on leaf2
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8002/public/v1/config/LLDPGlobal'

# enable LLDP on leaf3
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8003/public/v1/config/LLDPGlobal'

# enable LLDP on leaf4
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8004/public/v1/config/LLDPGlobal'

# enable LLDP on spine1
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8005/public/v1/config/LLDPGlobal'

# enable LLDP on spine2
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8006/public/v1/config/LLDPGlobal'
