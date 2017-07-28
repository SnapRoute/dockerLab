#!/usr/bin/python
import logging, logging.handlers, json, re, time
import subprocess, os, signal, sys, traceback, argparse
import threading
logger = logging.getLogger(__name__)

MAX_DEVICE_COUNT = 32
MAX_THREADS = 16
docker_image = "snapos/flex:latest"
netns_dir = "/var/run/netns/"
fs_image_dir = "./images/"
gen_flex_path = "/usr/local/flex.deb"
lab_doc_reg = "^[ ]*(?P<id>[^:]+):(?P<name>[^\n]+)\n(?P<desc>.*)"
device_name_reg = "^[a-zA-Z0-9\-\._]{2,64}$"
link_name_reg = "^(fpPort[0-9]{1,4})$"
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
    imageHelp = """
    Flexswitch image to run on the container. Image can be the full path to 
    .deb package or a url in which to download the image. By default, the
    flexswitch image bundled within the docker image will be deployed.
    """
    upgradeHelp = """
    Specify one or more container names to upgrade. To upgrade all containers
    within a specific lab, then use --upgrade "*" combined with --lab option.
    All containers will be upgraded to the flexswitch image provided by the
    --image option
    """
    doptHelp = """
    There may be additionally docker arguments that need to be passed to all
    containers.  The --dopt option is a string of additional options to be
    applied to the container when it is created.
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
    parser.add_argument("--image", action="store", dest="image", default=None,
        help=imageHelp, type=str)
    parser.add_argument("--upgrade", action="store", dest="upgrade",
        default=[], help=upgradeHelp, type=str, nargs="+")
    parser.add_argument("--cleanup", action="store_true", dest="cleanup",
        help="clean/delete all containers referenced within lab topology")
    parser.add_argument("--repair", action="store_true", dest="repair",
        help=repairHelp)
    parser.add_argument("--dopt", action="store", dest="dopt", default=None,
        help=doptHelp)
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
        fmt = "%(process)d:%(threadName)s||%(asctime)s.%(msecs).03d||%(levelname)s||"
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
        # exit code -2 seen on ctrl+c interrupt
        if e.returncode < 0: sys.exit("\nExiting...\n")
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
                    "connections": [], "interfaces":[], "pid":"",
                    "dockerimage":d.get("dockerimage", "snapos/flex:latest"),
                    "flexswitch":d.get("flexswitch", "_image_default_")
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

def container_is_running(device_name):
    """ return true if a container with provided name is currently running """

    cmd = "docker ps -qf name=%s" % device_name
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
        exec_cmd(cmd, ignore_exception=True)

def get_container_pid(device_name):
    """ based on container name, return corresponding docker pid """

    cmd = "docker inspect -f '{{.State.Pid}}' %s" % device_name
    pid = exec_cmd(cmd, ignore_exception=True)
    if pid is None:
        logger.error("failed to determine pid of %s, is it running?"%(
            device_name))
        return None
    return pid.strip()

def create_flexswitch_container(device_name, device_port, fs_image=None,
                                dopt=None, dockerimage=None):
    """ create flexswitch container with provided device_name. Calling
        function must call get_container_pid to reliably determine if 
        container was successfully started.
        Note, this function will first remove container if it currently exists
    """
    if dockerimage == None: dockerimage=docker_image
    # remove container if currently exists
    remove_flexswitch_container(device_name)

    # kickoff requested container
    logger.info("creating container %s" % device_name)
    cmd = "docker run -dt --log-driver=syslog --privileged --cap-add ALL "
    if fs_image is not None:
        cmd+= "--volume %s:%s:ro " % (fs_image, gen_flex_path)
    if dopt is not None: cmd+= "%s " % dopt
    cmd+= "--hostname=%s --name %s -p %s:8080 %s" % (
        device_name, device_name, device_port, dockerimage)
    out = exec_cmd(cmd, ignore_exception=True)
    if out is None:
        logger.error("failed to create docker container: %s, %s" % (
            device_name, device_port))
        return None
    return

def upgrade_flexswitch_container(device_name, fs_image):
    """ upgrade flexswitch image to provided fs_image using dpkg -i command
        since this is done live, no need to repair links on upgrade
        return boolean success
    """
    img_name = fs_image.split("/")[-1]
    logger.info("upgrading %s image to %s" % (device_name, img_name))

    # first verify container exists and is currently running
    if not container_is_running(device_name):
        logger.error("'%s' is not currently running" % device_name)
        return False

    # determine if a file is already mounted at gen_flex_path
    # if so, alert the user that upgrade will not be persistent across
    # container reset
    flex_image_mounted = False
    cmd = "docker inspect -f '{{json .Mounts}}' %s" % device_name
    js = exec_cmd(cmd)
    try:
        js = json.loads(js)
        for mount in js:
            logger.debug("mount: %s" % pretty_print(mount))
            if "Destination" in mount and mount["Destination"]==gen_flex_path:
                flex_image_mounted = True
                break
    except ValueError as e:
        logger.debug("failed to parse mount string: %s, assume mounted"%js)
        flex_image_mounted = True

    cmds = []
    cmds.append("docker cp %s %s:/%s" % (fs_image,device_name, img_name))
    cmds.append("docker exec -it %s dpkg -i /%s" % (device_name, img_name))
    if not flex_image_mounted:  
        cmds.append("docker exec -it %s mv /%s %s" % (
            device_name, img_name, gen_flex_path))
    else: 
        imsg = "mounted directory already exists at %s. " % gen_flex_path
        imsg+= "Upgrade will not be persistent across '%s' restart." % (
            device_name)
        logger.info(imsg)
    for c in cmds:
        out = exec_cmd(c, ignore_exception=True)
        if out is None:
            # only 'fail' if dpkg returned error, other errors are ok
            if not re.search(" dpkg -i ", c): continue
            logger.error("failed to upgrade %s" % device_name)
            return False
    return True

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

        # rename management interface to ma1 now that netns has been setup
        # rename_mgmt(pid1)

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

def rename_mgmt(pid1, s="eth0", d="ma1"):
    """ rename default eth0 interface to ma1. Operation for docker mgmt
        interface needs to be shut, rename, no-shut
    """
    cmds = []
    cmds.append("ip netns exec %s ip link set %s down" % (pid1, s))
    cmds.append("ip netns exec %s ip link set %s name %s" % (pid1,s, d))
    cmds.append("ip netns exec %s ip link set %s up" % (pid1,d))
    
    # execute commands
    for c in cmds: exec_cmd(c, ignore_exception=True)

def cleanup(topo):
    """ cleanup topology by deleting containers and removing links """
   
    threads = []
    for device_name in sorted(topo.keys()):
        t = threading.Thread(target=remove_flexswitch_container,
                args=(device_name, topo[device_name]["pid"], True))
        threads.append(t)
    execute_threads(threads)

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
        if devices[d].get("flexswitch", "_image_default_").upper() == "NA":
	    continue
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

def check_flexswitch_image(img=None):
    """ if image is a url, download the image and save to images/ cache 
        check that flexswitch image is formatted as docker deb package
            flexswitch_docker-(.*).deb
        return None if invalid else returns full image path
    """
    if img is None: return None
    img_reg = "^flexswitch_docker[a-z0-9\_\-\.]+\.deb$"
    # download image first if url is provided
    if re.search("^http", img) is not None:
        img_name = img.split("/")[-1]
        # validate img name (this will be repeated later again after download
        # but best if we skip the download if the image is not valid name)
        if not re.search(img_reg, img_name):
            logger.error("'%s' is not a valid flexswitch docker image"%img_name)
            return None
        # check if image is already available in fs_image_dir
        if not os.path.isfile("%s/%s" % (fs_image_dir, img_name)):
            logger.info("downloading image from %s" % img)
            ret = exec_cmd("wget -O %s/%s %s" % (fs_image_dir, img_name, img),
                ignore_exception=True)
            if ret is None:
                logger.error("failed to download image")
                try:
                    # wget -O creates file with zero size even on failed 
                    # download, need to delete it to prevent picking it up as 
                    # a cached copy
                    if os.path.isfile("%s/%s" % (fs_image_dir, img_name)):
                        logger.debug("deleting file: %s/%s" % (fs_image_dir, 
                            img_name))
                        os.remove("%s/%s" % (fs_image_dir, img_name))
                except IOError as e: pass
                return None
            # rename img to local file
            img = "%s/%s" % (fs_image_dir, img_name)

    # extract filename from path and ensure valid img name
    img_name = img.split("/")[-1]
    if not re.search(img_reg, img_name):
        logger.error("'%s' is not a valid flexswitch docker image" % img_name)
        return None
    if not os.path.isfile(img):
        # if file is not file, check the img_name against the cache directory
        # as last resort
        if not os.path.isfile("%s/%s" % (fs_image_dir, img_name)):
            logger.error("unable to access flexswitch image: %s" % img)
            return None
        else: img = "%s/%s" % (fs_image_dir, img_name)

    # verify size is not zero (1MB)
    if os.stat(img).st_size < 1024*1024*1:
        logger.error("invalid flexswitch image: %s, size: %s bytes"%(img_name, 
            os.stat(img).st_size))
        return None
    
    # everything looks ok, return full path
    return os.path.abspath(img)

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
                "name": r1.group("name").strip(),
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
    s+= "\n--lab %s\n  Name: %s\n  Stages: %s\n  Description:\n%s" % (
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
        except KeyboardInterrupt as e: sys.exit("\nExiting...\n")
        if not confirm:
            msg = "\nCannot continue while current containers exists.\n"
            msg+= "Please manually delete appropriate containers and then "
            msg+= "rerun this script\n"
            sys.exit(msg)

def execute_threads(threads):
    """ receive list of threading.Thread objects that have not yet been 
        started. Start each thread and Ensure that only MAX_THREADS are 
        running at a time. Ensure all threads complete
    """
    batch_count = 0
    logger.debug("execute %s threads batch-size:%s"%(len(threads),MAX_THREADS))
    while len(threads)>0:
        batch_count+=1
        active_threads = []
        while len(threads)>0 and len(active_threads) < MAX_THREADS:
            active_threads.append(threads.pop())
        # start batch of threads
        logger.debug("starting batch:%s" % batch_count)
        for t in active_threads:
            t.setDaemon(True)
            t.start()
            time.sleep(0.1)
        # wait until all threads end
        for t in active_threads: t.join()
        logger.debug("completed batch:%s (%s remaining)" % (batch_count, 
            len(threads)))

if __name__ == "__main__":

    try:
        # ensure script working directory is local directory
        os.chdir(os.path.dirname(os.path.realpath(__file__)))
    
        # verify we're running on Linux box
        out = exec_cmd("uname", ignore_exception=True)
        if out is None or "linux" not in out.lower():
            rmsg = "The underlying operating system is not Linux. "
            rmsg+= "Docker with flexswitch is not supported"
            sys.exit(rmsg)
    
        # get user arguments, setup logging, and get list of available labs
        args = get_args()
        setup_logger(logger, args)
        all_labs = get_labs()
    
        # handle describe options first
        if args.describe:
            # handle describe for single lab
            if args.lab is not None and args.lab.lower() in all_labs:
                print describe_lab(all_labs[args.lab.lower()])
            else:
                print "\nThe following %s labs are available:\n" % len(all_labs)
                for l in sorted(all_labs.keys()):
                    print describe_lab(all_labs[l])
            sys.exit()
    
        # verify user is running as root before preceeding further
        if os.geteuid() != 0:
            rmsg = "Sorry, you must be root. "
            rmsg+= "Use 'sudo python %s' to execute this script." % __file__
            sys.exit(rmsg)
    
        # check that docker is running
        if not check_docker_running():
            emsg = "Cannot connect to Docker daemon.  Is it running?\n"
            emsg+= "Try 'sudo service docker start' to enable the service"
            sys.exit(emsg)
    
        # verify flexswitch image is valid if provided
        if args.image is not None:
            args.image = check_flexswitch_image(args.image)
            if args.image is None:
                logger.error("flexswitch image validation failed")
                sys.exit(1)
    
        # handle upgrade option if requested
        upgrade_all = False
        if len(args.upgrade)>0:
            if args.image is None:
                emsg = "--image option required with --upgrade. "
                emsg+= "Use --help for more info"
                logger.error(emsg)
                sys.exit(1)
            if len(args.upgrade)==1 and args.upgrade[0]=="*":
                upgrade_all = True
            else:
                threads = []
                for device_name in args.upgrade:
                    t = threading.Thread(target=upgrade_flexswitch_container,
                        args=(device_name, args.image,))
                    threads.append(t)
                execute_threads(threads)
                #logger.info("completed upgrade of all selected device(s)")
                sys.exit()
    
        # all other operations required a --lab attribute. Ensure it's present.
        if args.lab is None:
            sys.exit("A lab name is required. Use --help for more information")
        if args.lab.lower() not in all_labs:
            emsg = "Lab '%s' not found. " % args.lab.lower()
            emsg+= "Use --describe to view currently available labs"
            sys.exit(emsg)
    
        # user selected lab
        current_lab = all_labs[args.lab.lower()]
    
        # check provided stage before doing any other work
        if args.stage > 0 and args.stage > current_lab["stage_max"]:
            emsg = "Stage %s is invalid for lab this lab (max:%s) " % (
                        args.stage, current_lab["stage_max"])
            emsg+= "Use --describe for lab details"
            sys.exit(emsg)
    
        # build/validate topology file from provided lab
        topo = get_topology("%s/topology.json" % current_lab["path"])
        if topo is None:
            logger.error("failed to parse device topology")
            sys.exit(1)
    
        # handle upgrade of all devices in lab
        if upgrade_all:
            threads = []
            for device_name in sorted(topo.keys()):
                t = threading.Thread(target=upgrade_flexswitch_container,
                    args=(device_name, args.image,))
                threads.append(t)
            execute_threads(threads)
            #logger.info("completed upgrade of all devices")
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
    
        # prepare for creating new containers...
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
        threads = []
        for device_name in sorted(topo.keys()):
            t = threading.Thread(target=create_flexswitch_container,
                args=(device_name, topo[device_name]["port"], args.image,
                args.dopt, topo[device_name].get("dockerimage", docker_image)))
            threads.append(t)
        execute_threads(threads)

        # gather pid for each device
        for device_name in topo:
            pid = get_container_pid(device_name)
            if pid is None: 
                logger.error("'%s' failed to start" % device_name)
                start_success = False
                break
            topo[device_name]["pid"] = pid
    
        # create topology connections
        if start_success:
            start_success = create_topology_connections(topo)
    
        if start_success:
            # verify/wait for flexswitch to start on all containers
            verify_flexswitch_running(topo)
            # apply stage configs
            if args.stage>0: execute_stages(current_lab["path"], args.stage)
            logger.info("Successfully started '%s'" % current_lab["name"])
        else:
            logger.error("failed to build topology, cleaning up...")
            cleanup(topo)

    except KeyboardInterrupt as e: 
        sys.exit("\nExiting...\n")
