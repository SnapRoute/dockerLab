#!/usr/bin/python
import logging, logging.handlers, json, re, time
import subprocess, os, signal, sys, traceback, argparse
logger = logging.getLogger(__name__)

MAX_DEVICE_COUNT = 32
docker_image = "snapos/flex:latest"
netns_dir = "/var/run/netns/"
lab_doc_reg = "^[ ]*(?P<id>[^:]+):(?P<name>[^\n]+)\n(?P<desc>.*)"
device_name_reg = "^[a-zA-Z0-9\-\._]{2,64}$"
link_name_reg = "^eth[0-9]{1,4}$"
link_state_reg = "^[0-9]+:[ ]*(?P<intf>[^@:]+)(@[^:]+)?:"

def get_args():
    """ get user arguments """

    desc = "SnapRoute LabTool"
   
    labHelp = """
    Specify which dockerized SnapRoute lab to build.  For a list of available
    labs and descriptions, use --describe option
    """
    labStageHelp= """
    Each lab may have one or more stages with various configurations/
    verifications to perform. Specify a stage option will auto-reconfigure 
    all devices with necessary configuration required at the end of the stage.
    This is a useful operation for users who need help completing and or wish
    to skip over stages. Note, this operation will rebuild the entire 
    container so any custom configuration will be lost.
    """
    repairHelp = """
    This script builds linux vEth interfaces and assigns them directly to the
    docker container to create the point-to-point links. If a container is
    reloaded, the vEth interface references become invalid and need to be 
    rebuilt.  Use the --repair option to repair broken topology links.
    """
     
    parser = argparse.ArgumentParser(description=desc,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--describe", action="store_true", dest="describe",
        help="Describe/List currently available labs")
    parser.add_argument("--lab", action="store", dest="lab", default=None, 
        help=labHelp)
    parser.add_argument("--stage", action="store", dest="stage", default=0,
        help=labStageHelp, type=int)
    parser.add_argument("--cleanup", action="store_true", dest="cleanup",
        help="clean/delete all containers referenced within lab topology")
    parser.add_argument("--repair", action="store_true", dest="repair",
        help=repairHelp)
    parser.add_argument("--debug", action="store", dest="debug",
        default="info", choices=["debug","warn","info","error"])

    # parse arguments
    args = parser.parse_args()
    return args

def pretty_print(js):
    """ try to convert json to pretty-print format """
    try:
        return json.dumps(js, indent=4, separators=(",", ":"), sort_keys=True)
    except Exception as e:
        return "%s" % js

def setup_logger(logger, args, quiet=False):
    """ setup logger with appropriate logging level and rotate options """

    # quiet all other loggers...
    if quiet:
        old_logger = logging.getLogger()
        old_logger.setLevel(logging.CRITICAL)
        for h in list(old_logger.handlers): old_logger.removeHandler(h)
        old_logger.addHandler(logging.NullHandler())

    # setting logging level
    if args.debug == "debug": logger.setLevel(logging.DEBUG)
    elif args.debug == "info": logger.setLevel(logging.INFO)
    elif args.debug == "warn": logger.setLevel(logging.WARNING)
    else: logger.setLevel(logging.ERROR)

    logger_handler = logging.StreamHandler(sys.stdout)
    if args.debug=="debug":
        fmt = "%(process)d||%(asctime)s.%(msecs).03d||%(levelname)s||"
        fmt+= "%(filename)s:(%(lineno)d)||%(message)s"
    else:
        fmt = "%(asctime)s  %(message)s"
        
    logger_handler.setFormatter(logging.Formatter(
        fmt=fmt,
        datefmt="%Z %Y-%m-%d %H:%M:%S")
    )
    # remove previous handlers if present
    for h in list(logger.handlers): logger.removeHandler(h)
    logger.addHandler(logger_handler)
    return logger

def exec_cmd(cmd, ignore_exception=False):
    """ execute command and return stdout output - None on error """
    try:
        logger.debug("excecuting command: %s" % cmd)
        out = subprocess.check_output(cmd,shell=True,stderr=subprocess.STDOUT)
        return out
    except subprocess.CalledProcessError as e:
        if ignore_exception: 
            logger.debug("error executing cmd: %s" % e)
            logger.debug("stderr: %s" % e.output)
            return None
        logger.warn("error executing cmd: %s" % cmd)
        logger.warn("%s" % e.output)
        raise e

def get_topology(topology_file = None):
    """ read in topology file, verify connections, and return new topology 
        dict in the following 
        format:
            "devices":{
                "device_name":{
                    "port":"",  # docker exposed port
                    "pid":"",   # docker pid once created
                    "connections": [
                        {"local-port":"","remote-device":"","remote-port":""}
                    ],
                    "interfaces": [] # list of interface names
                }
            }
        Note, the device with the lower name will record the connection so
        it's possible to have devices created with no connections
        (as 'remote' connection is in connection list of a different device)
    
        a valid topology_file must meet the following requirements:
            * between 2 and max_device_count devices
            * no duplicate links on any device
            * eth0 cannot be used on any link
            * no 'loopback' connections to the same device
    """
    try:
        with open(topology_file, "r") as f: js = json.load(f)
        devices = {}
        for attr in ["devices", "connections"]:
            if attr not in js or len(js[attr]) == 0 or \
                type(js[attr]) is not list:
                em = "invalid topology file. Expect '%s' attribute " % attr
                em+= "with type 'list' and length>0"
                logger.error(em)
                return None
        # build device list first
        for d in js["devices"]:
            if type(d) is not dict or "name" not in d or "port" not in d:
                logger.error("invalid device object: %s" % d)
                return None
            if not re.search(device_name_reg, d["name"]):
                logger.error("invalid device name '%s'" % dn)
                return None
            try:
                port = int(d["port"])
                if port >= 0xffff or port < 0x400:
                    logger.error("invalid port %s, must be between %d and %d"%(
                        port, 0x400, 0xffff))
                    return None
            except ValueError as e:
                logger.error("invalid port for %s, must be an integer" % d)
                return None
            # everything ok, add to devices
            devices[d["name"].lower()] = {
                    "name": d["name"], "port": int(d["port"]),
                    "connections": [], "interfaces":[], "pid":""
            }

        # build connections
        for c in js["connections"]:
            if type(c) is not dict or len(c.keys())!=2 or \
                (type(c[c.keys()[0]]) is not str and \
                type(c[c.keys()[0]]) is not unicode) or \
                len(c[c.keys()[0]])==0 or \
                (type(c[c.keys()[1]]) is not str and \
                type(c[c.keys()[1]]) is not unicode) or \
                len(c[c.keys()[1]])==0:
                logger.error("invalid connection: %s" % c)
                return None
            # verify device name and connection name
            d1,c1 = (c.keys()[0], c[c.keys()[0]])
            d2,c2 = (c.keys()[1], c[c.keys()[1]])
            d1_lower, d2_lower = (d1.lower(), d2.lower())
            if d1_lower not in devices:
                logger.error("device %s not in devices list" % d1_lower)
                return None
            if d2_lower not in devices:
                logger.error("device %s not in devices list" % d2_lower)
                return None
            for cn in (c1, c2):
                if not re.search(link_name_reg, cn):
                    logger.error("invalid connection name '%s'" % cn)
                    return None
            if d1_lower == d2_lower:
                logger.error("unsupported back-to-back connection: %s" % c)
                return None
            if c1 == "eth0" or c2 == "eth0":
                logger.error("eth0 is reserved for docker management: %s" % c)
                return None
            if c1 in devices[d1_lower]["interfaces"]:
                em = "device %s interface %s referenced multiple times" % (
                    d1_lower, c1)
                logger.error(em)
                return None
            if c2 in devices[d2_lower]["interfaces"]:
                em = "device %s interface %s referenced multiple times" % (
                    d2_lower, c2)
                logger.error(em)
                return None
            devices[d1_lower]["interfaces"].append(c1)
            devices[d2_lower]["interfaces"].append(c2)
            if d1_lower <= d2_lower:
                devices[d1_lower]["connections"].append({
                    "local-port":c1, "remote-port":c2,
                    "remote-device":d2_lower
                })
            else:
                devices[d2_lower]["connections"].append({
                    "local-port":c2, "remote-port":c1,
                    "remote-device":d1_lower
                })
    except IOError as e:
        logger.error("failed to open topology json file: %s" % (
            topology_file))
        return None
    except ValueError as e:
        logger.error("failed to parse topology json file: %s" % (
            topology_file))
        return None

    if len(devices) > MAX_DEVICE_COUNT:
        logger.error("Number of devices (%s) exceeds maximum count %s" % (
            len(devices), MAX_DEVICE_COUNT))
        return None
    elif len(devices) == 0:
        logger.error("No valid devices found in topology file")
        return None
    return devices

def check_docker_running():
    """ check if docker is running/successfully connect to it 
        return boolean success
    """
    logger.info("checking docker state")
    out = exec_cmd("docker ps", ignore_exception=True)
    return (out is not None)

def check_docker_image():
    """ check if docker_image is present.  If not, print info message and
        pull it down
    """
    img = docker_image.split(":")
    if len(img) == 2:
        if len(img[0]) == 0 or len(img[1]) == 0:
            raise Exception("invalid docker image name: %s" % docker_image)
        cmd = "docker images | egrep \"^%s \" | egrep \"%s\" | wc -l"%(
                img[0], img[1])
    else:
        cmd = "docker images | egrep \"^%s \" | " % docker_image
        cmd+= "egrep \"latest\" | wc -l"

    out = exec_cmd(cmd)
    if out.strip() == "0":
        linfo = "Downloading docker image: %s. " % docker_image
        linfo+= "This may take a few minutes..."
        logger.info(linfo)
        out = exec_cmd("docker pull %s" % docker_image)
    else:
        logger.debug("docker_image %s is present" % docker_image)

def container_exists(device_name):
    """ return true if a container (running or not running) with provided
        name already exists
    """ 
    cmd = "docker ps -aqf name=%s" % device_name
    return len(exec_cmd(cmd)) > 0

def remove_flexswitch_container(device_name, device_pid=None, force=False):
    """ check if container exists.  If so, remove it else do nothing """
    
    if not force: force = container_exists(device_name)
    if force:
        logger.info("removing existing container %s" % device_name)
        # remove soft links for pid
        if device_pid is not None and \
            os.path.isfile("%s/%s" % (netns_dir, device_pid)):
            logger.debug("removing netns pid: %s" % device_pid)
            cmd = "rm %s/%s" % (netns_dir, device_pid)
            exec_cmd(cmd, ignore_exception=True)
        cmd = "docker rm -f %s" % device_name
        exec_cmd(cmd)

def get_container_pid(device_name):
    """ based on container name, return corresponding docker pid """

    cmd = "docker inspect -f '{{.State.Pid}}' %s" % device_name
    pid = exec_cmd(cmd, ignore_exception=True)
    if pid is None:
        logger.error("failed to determine pid of %s, is it running?"%(
            device_name))
        return None
    return pid.strip()

def create_flexswitch_container(device_name, device_port):
    """ create flexswitch container with provided device_name and return
        PID of successfully created container.  Return none on error
        Note, this function will first remove container if it currently exists
    """
    # remove container if currently exists
    remove_flexswitch_container(device_name)

    # kickoff requested container
    logger.info("creating container %s" % device_name)
    cmd = "docker run -dt --log-driver=syslog --privileged --cap-add ALL "
    cmd+= "--hostname=%s --name %s -p %s:8080 %s" % (
        device_name, device_name, device_port, docker_image)
    out = exec_cmd(cmd, ignore_exception=True)
    if out is None:
        logger.error("failed to create docker container: %s, %s" % (
            device_name, device_port))
        return None
    return get_container_pid(device_name)

def repair_connections(topo):
    """ builds device to pid mapping and then executes 
        create_topology_connections to rebuild all connections
    """
    # map pids for each device within topology
    for device_name in topo:
        pid = None
        try: pid = get_container_pid(device_name)
        except Exception as e:
            logger.error("Error occurred: %s" % traceback.format_exc())
        if pid is not None and pid != "0" and pid!= "":
            topo[device_name]["pid"] = pid

    return create_topology_connections(topo)        

def create_topology_connections(topo):
    """ try to create all required topology connections. This operation
        does not stop on failure, it will try to create all connections
        in provided topology dictionary
        returns boolean - all connections successful
    """
    # first cleanup any stale connections
    try: clear_stale_connections()
    except Exception as e: pass

    all_connections_success = True
    for device_name in topo:
        pid1 = topo[device_name]["pid"]
        if pid1=="" or pid1=="0":
            logger.debug("skipping connections for non-operational device: %s"%(
                device_name))
            continue
        for c in topo[device_name]["connections"]:
            try:
                if c["remote-device"] not in topo:
                    logger.error("failed to map %s" % c)
                    logger.debug("topology: %s" % pretty_print(topo))
                    all_connections_success = False
                    continue
                pid2 = topo[c["remote-device"]]["pid"]
                if pid2 == "" or pid2 =="0": continue
                if connection_exists(pid1, pid2, c["local-port"],
                    c["remote-port"]):
                    logger.debug("skipping existing connection %s:%s - %s:%s"%(
                        device_name, c["local-port"], 
                        topo[c["remote-device"]]["name"], c["remote-port"]))
                    continue
                logger.info("creating connection  %s:%s - %s:%s" % (
                    device_name, c["local-port"], 
                    topo[c["remote-device"]]["name"], c["remote-port"]))
                create_connection(pid1, pid2, c["local-port"],c["remote-port"])
            except Exception as e:
                logger.error("Error occurred: %s" % traceback.format_exc())
                all_connections_success = False
    return all_connections_success

def connection_exists(pid1, pid2, link1, link2):
    """ returns True if connection already exists """

    link1_exists = False
    link2_exists = False
    out = exec_cmd("ip netns exec %s ip -o link" % pid1, ignore_exception=True)
    if out is not None:
        for l in out.split("\n"):
            r1 = re.search(link_state_reg, l.strip())
            if r1 is not None:
                if r1.group("intf") == link1: 
                    link1_exists = True
                    break
    out = exec_cmd("ip netns exec %s ip -o link" % pid2, ignore_exception=True)
    if out is not None:
        for l in out.split("\n"):
            r1 = re.search(link_state_reg, l.strip())
            if r1 is not None:
                if r1.group("intf") == link2: 
                    link2_exists = True
                    break
    return link1_exists and link2_exists
   
def create_connection(pid1, pid2, link1, link2):
    """ create connection between two docker containers """

    # verify pids and links
    if pid1 is None or pid2 is None or link1 is None or link2 is None or \
        len(pid1)==0 or len(pid2)==0 or len(link1)==0 or len(link2)==0:
        raise Exception("invalid connection arguments: %s, %s, %s, %s" % (
            pid1, pid2, link1, link2))

    # delete existing ethS/ethD in main namespace (ignore errors)
    exec_cmd("ip link delete ethS type veth", ignore_exception=True)
    exec_cmd("ip link delete ethD type veth", ignore_exception=True)

    # list of commands to execute
    cmds = ["mkdir -p %s" % netns_dir]

    # check if soft link exists, if not then create it
    if not os.path.isfile("%s/%s"%(netns_dir, pid1)):
        cmds.append("ln -s /proc/%s/ns/net %s/%s"%(
            pid1, netns_dir, pid1))
    if not os.path.isfile("%s/%s"%(netns_dir,pid2)):
        cmds.append("ln -s /proc/%s/ns/net %s/%s"%(
            pid2, netns_dir, pid2))

    # create connections
    cmds.append("ip link add ethS type veth peer name ethD")
    cmds.append("ip link set ethS netns %s" % pid1)
    cmds.append("ip link set ethD netns %s" % pid2)
    cmds.append("ip netns exec %s ip link set ethS name %s" % (pid1, link1))
    cmds.append("ip netns exec %s ip link set ethD name %s" % (pid2, link2))
    cmds.append("ip netns exec %s ip link set %s up" % (pid1, link1))
    cmds.append("ip netns exec %s ip link set %s up" % (pid2, link2))

    # execute commands
    for c in cmds: exec_cmd(c)

def clear_stale_connections():
    """ remove stale connection links in netns directory """
    logger.debug("cleaning up netns directory: %s" % netns_dir)
    for f in os.listdir(netns_dir):
        if not os.path.isfile("%s/%s" % (netns_dir, f)):
            logger.debug("removing stale softlink: %s/%s" % (netns_dir,f))
            os.remove("%s/%s" % (netns_dir, f))

def cleanup(topo):
    """ cleanup topology by deleting containers and removing links """

    for device_name in topo:
        try: remove_flexswitch_container(device_name, 
                device_pid=topo[device_name]["pid"], force=True)
        except Exception as e: pass
    try: clear_stale_connections()
    except Exception as e: pass

def execute_stages(path, stage=0):
    """ execute commands within all stage scripts from 0 to provided stage.
        Ensure only 'safe' curl commands are executed
    """
    for s in xrange(1, stage+1):
        fname = "%s/stage%s.sh" % (path,s)
        logger.info("applying stage %s configuration" % s)
        logger.debug("opening stage commands in %s" % fname)
        try:
            with open(fname, "r") as f:
                curl_commands = []
                for cmd in f.readlines():
                    cmd = cmd.strip()
                    if re.search("^curl[^|]+$", cmd) is not None:
                        logger.debug(exec_cmd(cmd, ignore_exception=True))
                    elif "curl" in cmd: 
                        logger.debug("skipping invalid cmd: %s" % cmd)
        except IOError as e:
            logger.error("failed to open %s: %s" % (fname,e)) 
            continue

def verify_flexswitch_running(devices, timeout=90, uptime_threshold=10):
    """ for provided devices dictionary, wait for flexswitch to start
        if it has not started within the timeout manually start the process
    """
    logger.info("waiting for flexswitch to start...")
    device_state = {}
    for d in devices: 
        device_state[d] = {"name":d, "uptime":0, "ready":False,
            "port":devices[d]["port"]}
    start_ts = time.time()
    while start_ts + timeout > time.time():
        # loop through all devices and check if sysd is currently running
        waiting = False
        for d in device_state:
            cmd ="curl -s 'http://localhost:%s/public/v1/state/SystemStatus'"%(
                device_state[d]["port"])
            out = exec_cmd(cmd, ignore_exception=True)
            if out is not None:
                try:
                    js = json.loads(out)
                    if "Object" in js and "UpTime" in js["Object"] and \
                        "Ready" in js["Object"]:
                        uptime = js["Object"]["UpTime"]
                        ready = bool(js["Object"]["Ready"])
                        logger.debug("uptime for %s: %s, ready:%r" % (d, 
                            uptime, ready))
                        device_state[d]["uptime"] = uptime
                        # overwrite ready attribute if uptime is less than
                        # threshold
                        if "ms" in uptime: ready = False
                        elif "h" in uptime or "m" in uptime: pass
                        else:
                            ut = float(re.sub("s","", uptime))
                            if ut < uptime_threshold: ready = False
                        logger.debug("overwriting ready to: %r" % ready)
                        device_state[d]["ready"] = ready
                        if ready: continue
                               
                except ValueError as e:
                    logger.debug("failed to parse: %s" % e)
                    device_state[d]["ready"] = False
                    device_state[d]["uptime"] = 0
            # only if all conditions match do we skip reset of waiting flag
            waiting = True
        if waiting: time.sleep(1)
        else: break
    
    # check if any devices need to have flexswitch manually started
    manually_started = False
    for d in device_state:
        if not device_state[d]["ready"]:
            manually_started = True
            logger.info("timeout expired, restarting flexswitch on %s"%d)
            exec_cmd("docker exec -it %s service flexswitch start" % d)

    # best to go through process again to ensure service actually starts
    if manually_started:
        return verify_flexswitch_running(devices, timeout, uptime_threshold)
    # success
    logger.info("flexswitch is running on all containers")

def get_labs():
    """ use package docstring to determine lab id, name, and description 
        return dictionary containing {
            "lab_id": {
                "id": <lab_id>,
                "name": <lab_name>,
                "description": <lab_description>,
                "path": <full path to lab module>,
                "stage_max": <integer maximum number of stages for lab>
            }
        }
    """
    from labs import labs
    all_labs = {}
    for l in labs:
        r1 = re.search(lab_doc_reg, l.__doc__, re.DOTALL)
        if r1 is not None:
            # ensure all stages from 1 to max are present (zero never present)
            stages = []
            valid_stages = True
            stage_max = 0
            for f in os.listdir(l.__path__[0]):
                r2 = re.search("^stage(?P<stage>[0-9]+)\.sh$", f)
                if r2 is not None: 
                    s = int(r2.group("stage"))
                    if s > stage_max: stage_max = s
                    stages.append(s)
            for s in xrange(1, stage_max+1):
                if s not in stages:
                    logger.error("missing stage %s in lab '%s'" % (
                        s, r1.group("name")))
                    valid_stages = False
                    break
            if not valid_stages: continue
            lab_id = re.sub(" ","_", r1.group("id").lower().strip())
            all_labs[lab_id] = {
                "id": lab_id,
                "name": r1.group("name"),
                "description": r1.group("desc"),
                "path": l.__path__[0],
                "stage_max": stage_max
            }
        else:
            logger.error("failed to parse docstring for lab: %s"%l.__file__)
    return all_labs

def describe_lab(lab):
    """ common formatting for lab description """
    s = "*"*80
    s+= "\n--lab %s\n  Name:%s\n  Stages: %s\n  Description:\n%s" % (
            lab["id"], lab["name"], lab["stage_max"], lab["description"])
    return s

def prompt_for_container_delete(topo):
    """ check if any container with device_name already exists, if so notify
        user that they will be deleted in order to continue with script.
        If user does not confirm, exist script
    """
    existing_containers = []
    for device_name in sorted(topo.keys()):
        if container_exists(device_name): 
            existing_containers.append(device_name)

    if len(existing_containers) > 0:
        print "\nThe following containers already exist:"
        for c in existing_containers: print "\t%s" % c
        msg = "You can see more details on each container by issuing "
        msg+= "'docker ps -a'"
        print msg
        confirm = None
        prompt = "Do you want to delete the current containers? [yes/no] "
        try:
            while confirm is None:
                confirm = ("%s" % raw_input(prompt)).strip()
                if re.search("^y(es|e)?$", confirm, re.IGNORECASE):
                    confirm = True
                elif re.search("^no?$", confirm, re.IGNORECASE):
                    confirm = False
                else:
                    print "Please type 'yes' or 'no'"
                    confirm = None
        except KeyboardInterrupt as e: sys.exit("\n")
        if not confirm:
            msg = "\nCannot continue while current containers exists.\n"
            msg+= "Please manually delete appropriate containers and then "
            msg+= "rerun this script\n"
            sys.exit(msg)

if __name__ == "__main__":
 
    # ensure script working directory is local directory
    os.chdir(os.path.dirname(os.path.realpath(__file__)))

    # verify we're running on Linux box
    out = exec_cmd("uname", ignore_exception=True)
    if out is None or "linux" not in out.lower():
        rmsg = "The underlying operating system is not Linux. "
        rmsg+= "Docker with flexswitch is not supported"
        sys.exit(rmsg)
    # verify user is running as root
    if os.geteuid() != 0:
        rmsg = "Sorry, you must be root. "
        rmsg+= "Use 'sudo python %s' to execute this script." % __file__
        sys.exit(rmsg)
 
    # get user arguments, setup logging, and get list of available labs
    args = get_args()
    setup_logger(logger, args)
    all_labs = get_labs()

    # handle refresh/describe options first
    if args.describe and not args.lab:
        print "\nThe following %s labs are available:\n" % len(all_labs)
        for l in sorted(all_labs.keys()):
            print describe_lab(all_labs[l])
        sys.exit()

    # all other operations required a --lab attribute. Ensure it's present.
    if args.lab is None:
        sys.exit("A lab name is required. Use --help for more information")
    if args.lab.lower() not in all_labs:
        emsg = "Lab '%s' not found.  Use --describe to view " % args.lab.lower()
        emsg+= "currently available labs"
        sys.exit(emsg)
    current_lab = all_labs[args.lab.lower()]
    if args.describe:
        print describe_lab(current_lab)
        sys.exit()

    # check provided stage before doing any other work
    if args.stage > 0 and args.stage > current_lab["stage_max"]:
        emsg = "Stage %s is invalid for lab this lab (max:%s)" % (
                    args.stage, current_lab["stage_max"])
        emsg+= "Use --describe for lab details"
        sys.exit(emsg)

    # check that docker is running
    if not check_docker_running():
        emsg = "Cannot connect to Docker daemon.  Is it running?\n"
        emsg+= "Try 'sudo service docker start' to enable the service"
        sys.exit(emsg)

    # build/validate topology file from provided lab
    topo = get_topology("%s/topology.json" % current_lab["path"])
    if topo is None:
        logger.error("failed to parse device topology")
        sys.exit(1)

    # perform cleanup option if requested
    if args.cleanup:
        logger.info("cleaning up existing containers")
        cleanup(topo)
        sys.exit()

    # repair broken connections if requested
    if args.repair:
        logger.info("repairing connections for running containers")
        repair_connections(topo)
        sys.exit()

    # if script is executed without a stage option, then notify user of
    # any containers that will be automatically deleted 
    if args.stage == 0:
        prompt_for_container_delete(topo)

    # check if flexswitch is present, if not perform docker pull
    try: check_docker_image() 
    except Exception as e:
        logger.error("Failed to verify/pull docker image: %s" % e)
        sys.exit(1) 

    # create containers and map pid to each device in topology
    start_success = True
    for device_name in topo:
        pid = None
        try: pid = create_flexswitch_container(device_name, 
                topo[device_name]["port"]) 
        except Exception as e:
            logger.error("Error occurred: %s" % traceback.format_exc())
        if pid is None:
            start_success = False
            break
        topo[device_name]["pid"] = pid
    
    # create topology connections 
    if start_success: 
        start_success = create_topology_connections(topo)

    if start_success:
        # verify/wait for flexswitch to start on all containers
        try: verify_flexswitch_running(topo)
        except KeyboardInterrupt as e: sys.exit("\n")
        # apply stage configs
        if args.stage>0: execute_stages(current_lab["path"], args.stage)
        logger.info("Successfully started '%s'" % current_lab["name"])
    else:
        logger.error("failed to build topology, cleaning up...")
        cleanup(topo)
