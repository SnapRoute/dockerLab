#!/bin/bash
# stage scripts execute command outside of container instance on custom port

# configure BGP AS and neighbors on leaf1
curl -sX PATCH -d '{"ASNum":"65001","RouterId":"10.0.0.1"}' 'http://localhost:8001/public/v1/config/BGPGlobal'
curl -sX POST -d '{"NeighborAddress":"10.1.1.2","PeerAS":"65002","UpdateSource":"10.1.1.1"}' 'http://localhost:8001/public/v1/config/BGPv4Neighbor'
curl -sX POST -d '{"NeighborAddress":"10.1.3.2","PeerAS":"65003","UpdateSource":"10.1.3.1"}' 'http://localhost:8001/public/v1/config/BGPv4Neighbor'


# configure BGP AS and neighbors on leaf2
curl -sX PATCH -d '{"ASNum":"65002","RouterId":"10.0.0.2"}' 'http://localhost:8002/public/v1/config/BGPGlobal'
curl -sX POST -d '{"NeighborAddress":"10.1.1.1","PeerAS":"65001","UpdateSource":"10.1.1.2"}' 'http://localhost:8002/public/v1/config/BGPv4Neighbor'
curl -sX POST -d '{"NeighborAddress":"10.1.2.2","PeerAS":"65003","UpdateSource":"10.1.2.1"}' 'http://localhost:8002/public/v1/config/BGPv4Neighbor'


# configure BGP AS and neighbors on leaf3
curl -sX PATCH -d '{"ASNum":"65003","RouterId":"10.0.0.3"}' 'http://localhost:8003/public/v1/config/BGPGlobal'
curl -sX POST -d '{"NeighborAddress":"10.1.3.1","PeerAS":"65001","UpdateSource":"10.1.3.2"}' 'http://localhost:8003/public/v1/config/BGPv4Neighbor'
curl -sX POST -d '{"NeighborAddress":"10.1.2.1","PeerAS":"65002","UpdateSource":"10.1.2.2"}' 'http://localhost:8003/public/v1/config/BGPv4Neighbor'

