
## Easy Setup

Setup your SnapRoute dockerLab environment with a single command:

```bash

root@ubuntu:~/$ curl -sSL https://raw.githubusercontent.com/SnapRoute/dockerLab/master/bash/install.sh | sh

```

## Manual Setup

The SnapRoute docker lab is dependent on a Linux kernel locally running docker 
service and python 2.7. Additionally, it's useful to have git installed to 
pull fresh lab modules.

Use apt-get, yum, or pkg to install
* docker
* python2.7
* git

Finally, pull the public repository via git clone command.  For example:

```bash
# install git and python
root@ubuntu:~/$ apt-get update && apt-get install -y git python

# install docker via get.docker.com script
root@ubuntu:~/$ curl -sSL https://get.docker.com/ | sh
root@ubuntu:~/$ service docker start

# git clone to pull dockerLab scripts
root@ubuntu:~/$ git clone https://github.com/SnapRoute/dockerLab.git
root@ubuntu:~/$ python dockerLab/labtool.py --help

```

## Usage

Once docker is installed, you can execute  **labtool.py** to spin up containers
running SnapRoute Flexswitch.  

### Available Labs:
* [Lab1: Introduction to Flexswitch](./labs/lab1/README.md)

```bash

root@ubuntu:~/$ python dockerLab/labtool.py --help
usage: labtool.py [-h] [--describe] [--lab LAB] [--stage STAGE] [--cleanup]
                  [--repair] [--debug {debug,warn,info,error}]

SnapRoute LabTool

optional arguments:
  -h, --help            show this help message and exit
  --describe            Describe/List currently available labs
  --lab LAB             Specify which dockerized SnapRoute lab to build. For a
                        list of available labs and descriptions, use
                        --describe option
  --stage STAGE         Each lab may have one or more stages with various
                        configurations/ verifications to perform. Specify a
                        stage option will auto-reconfigure all devices with
                        necessary configuration required at the end of the
                        stage. This is a useful operation for users who need
                        help completing and or wish to skip over stages. Note,
                        this operation will rebuild the entire container so
                        any custom configuration will be lost.
  --cleanup             clean/delete all containers referenced within lab
                        topology
  --repair              This script builds linux vEth interfaces and assigns
                        them directly to the docker container to create the
                        point-to-point links. If a container is reloaded, the
                        vEth interface references become invalid and need to
                        be rebuilt. Use the --repair option to repair broken
                        topology links.
  --debug {debug,warn,info,error}

```
