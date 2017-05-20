#!/bin/bash
# stage scripts execute command outside of container instance on custom port

# enable LLDP on all leaves
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8001/public/v1/config/LLDPGlobal'
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8002/public/v1/config/LLDPGlobal'
curl -sX PATCH -d '{"Enable":true}' 'http://localhost:8003/public/v1/config/LLDPGlobal'
