# Custom Topologies

Create custom labs and topologies to emulate your network. This tutorial walks you through a simple example to help you get started.

For our custom topology, we will use a CLOS network with two spines and four leaves. Additionally, we will connect two ubuntu hosts to leaf1 and leaf4 as shown below:

![Lab 2 Diagram](lab2_diagram.png)

## Step 1: Create a Package Directory for your Lab

1. Create a folder under dockerLabs/labs/ directory.  
We'll use the name 'lab2'.
	 
```bash
user1@ubuntu:~$ cd dockerLab/labs
user1@ubuntu:~/dockerLab/labs$ mkdir lab2
```  
  
2. Create an **\_\_init\_\_.py** file with a docstring that 
describes our lab. This allows lab2 to appear as a 
discoverable package to  **labtool**.
	
The first line of the docstring must be in the format of
_id:Name_ and a multiline description can follow after. For example:

Ensure you are in the lab2 directory:

```bash
user1@ubuntu:~/dockerLab/labs/lab2$ 

user1@ubuntu:~/dockerLab/labs/lab2$ echo '"""
> lab2: my custom lab
> Check out this description of my custom lab!
> """' > __init__.py

user1@ubuntu:~/dockerLab/labs/lab2$ cat __init__.py
"""
lab2: my custom lab
Check out this description of my custom lab!
"""
```

## Step 2: Create the Topology File

Next, we'll need to build the topology file. The topology file is a json
 file requiring  _devices_ attributes and a _connections_ attribute. It must be named _**topology.json**_.

Each device can contain the following string attributes:
* name: (required) name of the device
* port: (required) externally exposed host port
* internal\_port: (optional, default:8080) internal port mapped to external host port
* dockerimage: (optional, default:snapos/flex:latest) docker image to deploy on container
* flexswitch: (optional) if a custom non-flexswitch dockerimage is specified then this value must be 'NA'
* schema: (optional, default: http): http or https schema to use when connecting to flexswitch device.  
* username: (optional, default: admin): basic auth username credential
* password: (optional, default: snaproute): basic auth password credential

Each connection will contain a source device, source port, destination device, and a destination port.

The flexswitch API is exposed on port 8080 on each device. To reach this port from outside the container, **labtool** maps port internal port 8080 on each container to the port defined in the topology file.  Our lab uses the following mappings:

| Device   | Internal Container Port | Host Port |
| -------- |:-----------------------:| ---------:|
| leaf1    | 8080                    | 8001      |
| leaf2    | 8080                    | 8002      |
| leaf3    | 8080                    | 8003      |
| leaf4    | 8080                    | 8004      |
| spine1   | 8080                    | 8005      |
| spine2   | 8080                    | 8006      |
| host1    | 22                      | 8007      |
| host2    | 22                      | 8008      |

Create the _**topology.json**_ file and copy it to the lab2 directory

```bash
user1@ubuntu:~/dockerLab/labs/lab2$ cat topology.json
{
    "devices":[
        {"name":"leaf1", "port":"8001"},
        {"name":"leaf2", "port":"8002"},
        {"name":"leaf3", "port":"8003"},
        {"name":"leaf4", "port":"8004"},
        {"name":"spine1", "port":"8005"},
        {"name":"spine2", "port":"8006"},
        {"name":"host1",  "port":"8007", "port_internal":"22",
            "dockerimage":"ubuntu:16.04", "flexswitch":"NA"
        },
        {"name":"host2",  "port":"8008", "port_internal":"22",
            "dockerimage":"ubuntu:16.04", "flexswitch":"NA"
        }
    ],
    "connections":[
        {"spine1":"fpPort1","leaf1":"fpPort1"},
        {"spine1":"fpPort2","leaf2":"fpPort1"},
        {"spine1":"fpPort3","leaf3":"fpPort1"},
        {"spine1":"fpPort4","leaf4":"fpPort1"},
        {"spine2":"fpPort1","leaf1":"fpPort2"},
        {"spine2":"fpPort2","leaf2":"fpPort2"},
        {"spine2":"fpPort3","leaf3":"fpPort2"},
        {"spine2":"fpPort4","leaf4":"fpPort2"},
        {"leaf1" :"fpPort3", "host1":"eth1"},
        {"leaf4" :"fpPort3", "host2":"eth1"}
    ]
}
```

## Step 3: (Optional) Create stage files

If you would like to stage configurations for your lab, create 
stage files that apply the needed configuration to each device. The 
files must be named _stage<#>.sh_, and must be created in sequential order.

The stage files are always executed in order.  For example, if there are
two stage files (stage1.sh and stage2.sh), and the user executes the 
custom lab with _--stage 1_ option, all curl commands in stage1.sh will be applied.  If the user executes the custom lab with _--stage 2_ option, all curl commands in stage1.sh will be applied followed by all curl
commands in stage2.sh

For the example lab, we will create a _stage1.sh_ file that enables LLDP on all devices.  

!!! Note
	The commands are executed from outside the container so the http port number in the curl command is unique to each device.

```bash
user1@ubuntu:~/dockerLab/labs/lab2$ cat stage1.sh
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
```

The staging bash scripts can access device information (container name, pid, port information, schema, and credentials) by sourcing the auto-generated source.env file created at lab runtime.  The file will be created in a hidden folder under the lab directory called '.generated'.  For example, after executing this lab the environment file will be as follows:

```bash
user1@ubuntu:~/dockerLab$ 
cat labs/lab2/.generated/source.env
HOST1_NAME=host1
HOST1_PASSWORD=snaproute
HOST1_PID=2564
HOST1_PORT=8007
HOST1_SCHEMA=http
HOST1_USERNAME=admin
<snip>
SPINE1_NAME=spine1
SPINE1_PASSWORD=snaproute
SPINE1_PID=1618
SPINE1_PORT=8005
SPINE1_SCHEMA=http
SPINE1_USERNAME=admin
SPINE2_NAME=spine2
SPINE2_PASSWORD=snaproute
SPINE2_PID=1415
SPINE2_PORT=8006
SPINE2_SCHEMA=http
SPINE2_USERNAME=admin
```


## Run It

At this point, **labtool** detects the custom topology and corresponding stages.

```bash
user1@ubuntu:~/dockerLab$ sudo ./labtool.py --describe --lab lab2
********************************************************************************
--lab lab2
  Name: An Example Custom Topology
  Stages: 1
  Description:
Create custom topology and staging files to emulate your network. See the
documentation under the lab2 for more detailsA

```

Run our custom topology:

```
user1@ubuntu:~/dockerLab$ sudo ./labtool.py --lab lab2 --stage 1
EDT 2017-08-03 17:41:37  checking docker state
EDT 2017-08-03 17:41:37  Downloading docker image: ubuntu:16.04. This may take a few minutes...
EDT 2017-08-03 17:41:52  Downloading docker image: snapos/flex:latest. This may take a few minutes...
EDT 2017-08-03 17:42:33  creating container spine2 using snapos/flex:latest
EDT 2017-08-03 17:42:33  creating container spine1 using snapos/flex:latest
EDT 2017-08-03 17:42:33  creating container leaf4 using snapos/flex:latest
EDT 2017-08-03 17:42:33  creating container leaf3 using snapos/flex:latest
EDT 2017-08-03 17:42:34  creating container leaf2 using snapos/flex:latest
EDT 2017-08-03 17:42:34  creating container leaf1 using snapos/flex:latest
EDT 2017-08-03 17:42:34  creating container host2 using ubuntu:16.04
EDT 2017-08-03 17:42:34  creating container host1 using ubuntu:16.04
EDT 2017-08-03 17:42:35  creating connection  host1:eth1 - leaf1:fpPort3
EDT 2017-08-03 17:42:35  creating connection  leaf4:fpPort1 - spine1:fpPort4
EDT 2017-08-03 17:42:36  creating connection  leaf4:fpPort2 - spine2:fpPort4
EDT 2017-08-03 17:42:36  creating connection  leaf1:fpPort1 - spine1:fpPort1
EDT 2017-08-03 17:42:37  creating connection  leaf1:fpPort2 - spine2:fpPort1
EDT 2017-08-03 17:42:37  creating connection  host2:eth1 - leaf4:fpPort3
EDT 2017-08-03 17:42:38  creating connection  leaf3:fpPort1 - spine1:fpPort3
EDT 2017-08-03 17:42:38  creating connection  leaf3:fpPort2 - spine2:fpPort3
EDT 2017-08-03 17:42:39  creating connection  leaf2:fpPort1 - spine1:fpPort2
EDT 2017-08-03 17:42:39  creating connection  leaf2:fpPort2 - spine2:fpPort2
EDT 2017-08-03 17:42:39  waiting for flexswitch to start...
EDT 2017-08-03 17:44:08  flexswitch is running on all containers
EDT 2017-08-03 17:44:08  applying stage 1 configuration
EDT 2017-08-03 17:44:08  Successfully started 'An Example Custom Topology'

```


