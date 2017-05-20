#!/bin/bash
# stage scripts execute command outside of container instance on custom port

# Redistribute all connected routes into BGP on leaf1
curl -sX POST  -d '{"Name":"s1_permit","Action":"permit"}' 'http://localhost:8001/public/v1/config/PolicyStmt'
curl -sX POST -d '{"Name":"p1_match_all","StatementList":[{"Priority":0,"Statement":"s1_permit"}]}' 'http://localhost:8001/public/v1/config/PolicyDefinition'
curl -sX PATCH -d '{"Redistribution":[{"policy":"p1_match_all","Sources":"CONNECTED"}]}' 'http://localhost:8001/public/v1/config/BGPGlobal'


# Redistribute all connected routes into BGP on leaf2
curl -sX POST  -d '{"Name":"s1_permit","Action":"permit"}' 'http://localhost:8002/public/v1/config/PolicyStmt'
curl -sX POST -d '{"Name":"p1_match_all","StatementList":[{"Priority":0,"Statement":"s1_permit"}]}' 'http://localhost:8002/public/v1/config/PolicyDefinition'
curl -sX PATCH -d '{"Redistribution":[{"policy":"p1_match_all","Sources":"CONNECTED"}]}' 'http://localhost:8002/public/v1/config/BGPGlobal'


# Redistribute all connected routes into BGP on leaf3
curl -sX POST  -d '{"Name":"s1_permit","Action":"permit"}' 'http://localhost:8003/public/v1/config/PolicyStmt'
curl -sX POST -d '{"Name":"p1_match_all","StatementList":[{"Priority":0,"Statement":"s1_permit"}]}' 'http://localhost:8003/public/v1/config/PolicyDefinition'
curl -sX PATCH -d '{"Redistribution":[{"policy":"p1_match_all","Sources":"CONNECTED"}]}' 'http://localhost:8003/public/v1/config/BGPGlobal'

