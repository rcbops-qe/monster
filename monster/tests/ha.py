"""
Module to test High Availability in RPC
"""
import os
import sys
import socket
from time import sleep
from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client

from monster import util
from monster.util import Logger
from monster.util import xunit_merge
from monster.tests.test import Test


logger = Logger("hatest")
logger.set_log_level("INFO")

class Creds(object):
    """
    Openstack cred object
    """
    def __init__(self, user, password, url):
        self.user = user
        self.password = password
        self.url = url


class Build(object):
    """
    Build state to be verified after failover
    """
    def __init__(self, server, network_id, subnet_id, name, image, flavor):
        self.server = server
        self.name = name
        self.image = image
        self.flavor = flavor
        self.network_id = network_id
        self.subnet_id = subnet_id
        self.ip_info = None
        self.router_id = None

    def destroy(self, nova, neutron):
        """
        Cleans up build state from OpenStack
        """
#float     neutron floatingip-delete [floatingip-id]
#instance  nova delete [instance-id]
#iface     neutron router-interface-delete [router-id] [subnet-id]
#router    neutron router-delete [router-id]
#subnet    neutron subnet-delete [subnet-id]
#network   neutron net-delete [network-id]
        logger.info('Cleaning up instance and network clutter...')

        logger.debug('Deleting floating IP')
        deleted = False
        while not deleted:
            try:
                neutron.delete_floatingip(self.ip_info['id'])
                deleted = True
            except:
                deleted = False

        logger.debug('Deleting server')
        deleted = False
        while not deleted:
            try:
                nova.servers.delete(self.server)
                deleted = True
            except:
                deleted = False

        logger.debug('Deleting router interface')
        deleted = False
        while not deleted:
            try:
                neutron.remove_interface_router(self.router_id,
                                                {"subnet_id": self.subnet_id})
                deleted = True
            except:
                deleted = False

        logger.debug("Deleting router")
        deleted = False
        while not deleted:
            try:
                neutron.delete_router(self.router_id)
                deleted = True
            except:
                deleted = False

        logger.debug("Deleting subnet")
        deleted = False
        while not deleted:
            try:
                neutron.delete_subnet(self.subnet_id)
                deleted = True
            except:
                deleted = False

        logger.debug("Deleting network")
        deleted = False
        while not deleted:
            try:
                neutron.delete_network(self.network_id)
                deleted = True
            except:
                deleted = False


class HATest(Test):
    """
    HA Openstack tests
    """
    def __init__(self, deployment):
        super(HATest, self).__init__(deployment)
        self.iterations = 1
        self.current_iteration = 0
        controllers = list(self.deployment.search_role("controller"))
        self.controller1 = controllers[0]
        self.controller2 = controllers[1]

        # get creds
        creds = self.gather_creds(deployment)

        # Setup clients
        self.provider_net = None
        self.nova = nova_client.Client(creds.user, creds.password, creds.user,
                                       auth_url=creds.url)
        self.neutron = neutron_client(auth_url=creds.url, username=creds.user,
                                      password=creds.password,
                                      tenant_name=creds.user)
        self.rabbit = deployment.rabbitmq_mgmt_client

    @property
    def name(self):
        return "High Availability tests"

    def gather_creds(self, deployment):
        """
        Creates cred object based off deployment
        """
        keystone = deployment.environment.override_attributes['keystone']
        user = keystone['admin_user']
        users = keystone['users']
        password = users[user]['password']
        url = self.controller1['keystone']['adminURL']
        creds = Creds(user, password, url)
        return creds

    def instance_cmd(self, server_id, net_id, cmd):
        """
        Logs into instance using net namespace
        """
        namespace = "qdhcpd-{0}".format(net_id)
        server = self.nova.servers.get(server_id)
        server_ip = server['server']['ipaddress']
        icmd = ("ip netns exec {0} bash; "
                "ssh -o UseprKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no "
                "-i ~/.ssh/testkey {1}; "
                "{2}").format(namespace, server_ip, cmd)
        server.run_cmd(icmd)

    def create_router(self, router_name, admin_state_up=True):
        """
        Creates a neutron router
        """
        new_router = {"router": {
                      "name": router_name,
                      "admin_state_up": admin_state_up}}
        router = self.neutron.create_router(new_router)
        return router['router']['id']

    def create_network(self, network_name):
        """
        Creates a neutron network
        """
        new_net = {"network": {"name": network_name, "shared": True}}
        net = self.neutron.create_network(new_net)
        return net['network']['id']

    def create_subnet(self, subnet_name, network_id, subnet_cidr):
        """
        Creates a neutron subnet
        """
        new_subnet = {"subnet": {
            "name": subnet_name, "network_id": network_id,
            "cidr": subnet_cidr, "ip_version": "4"}}
        subnet = self.neutron.create_subnet(new_subnet)
        return subnet['subnet']['id']

    def add_router_interface(self, router_id, subnet_id):
        """
        Adds an interface to a given router
        """
        subnet_iface = {"subnet_id": subnet_id}
        iface = self.neutron.add_interface_router(router_id, subnet_iface)
        return iface['port_id']

    def keepalived_fail(self, node):
        """
        Simulates failure with keepalived
        """
        node.run_cmd("service keepalived stop")

    def keepalived_restore(self, node):
        """
        Simulates failback with keepalived
        """
        node.run_cmd("service keepalived start")

    def move_vips_from(self, node_up):
        """
        Moves vips from controller using keepalived
        """
        logger.info('Restarting keepalived...')
        self.keepalived_fail(node_up)
        sleep(5)
        self.keepalived_restore(node_up)
        sleep(10)

    def fail_node(self, node):
        """
        Failover a node
        """
        logger.info('Powering off node...')
        node.power_off()

    def is_online(self, ip):
        """
        Returns true if a connection can be made with ssh
        """
        logger.info("Checking if {0} is online".format(ip))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(2)
            s.connect((ip, 22))
            s.close()
        except socket.error:
            logger.debug('There was a socket error')
            return False
        logger.debug("{0} is online".format(ip))
        return True

    def build(self, server_name, server_image, server_flavor, network_name,
              subnet_name, router_name, cidr):
        """
        Builds state in OpenStack (net, server)
        """
        logger.info("Configuring network and building instance...")

        logger.debug("Creating network: {0}".format(network_name))
        network_id = self.create_network(network_name)
        logger.debug("Network ({0}) created".format(network_id))

        logger.debug("Creating subnetwork: {0}".format(subnet_name))
        subnet_id = self.create_subnet(subnet_name, network_id, cidr)
        logger.debug("Subnet ({0}) created".format(subnet_id))

        logger.debug("Creating router: {0}".format(router_name))
        router_id = self.create_router(router_name)
        logger.debug("Router ({0}) created".format(router_id))

        logger.debug('Creating router interface')
        iface_port = self.add_router_interface(router_id, subnet_id)
        logger.debug("Interface port: {0}".format(iface_port))
#-----------------------------------------------------------------------------
        provider_net_id = self.provider_net
        self.neutron.add_gateway_router(router_id,
                                        body={"network_id": provider_net_id})
#-----------------------------------------------------------------------------
        networks = [{"net-id": network_id}]
        logger.debug("Building server with above network configuration")
        server = False
        while not server:
            try:
                logger.debug("Executing server creation command")
                server = self.nova.servers.create(server_name, server_image,
                                                  server_flavor, nics=networks)
                logger.debug("Server creation command executed")
            except:
                server = False
                logger.debug("Server creation command failed epicly!")
                logger.debug("The epicness of its failure was truly a "
                                  "sight to behold...")
                sleep(1)

        build_status = "BUILD"
        while build_status == "BUILD":
            build_status = self.nova.servers.get(server.id).status
        if build_status == "ERROR":
            logger.error("Server ({0}) entered ERROR status!".format(
                              server_name))
            assert (build_status == "ERROR"), "Server failed to initialize!"
        else:
            logger.debug("Server ({0}) status: {1}".format(server_name,
                                                                build_status))
        build = Build(server, network_id, subnet_id, server_name,
                      server_image, server_flavor)
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
        port_id = ""
        while not port_id:
            logger.debug("Attempting to get a valid port id...")
            port_id = self.get_port_id(build)

        floating_ip = self.neutron.create_floatingip({"floatingip":
                                                     {"floating_network_id":
                                                      provider_net_id,
                                                      "port_id": port_id}})
        build.ip_info = floating_ip['floatingip']
        build.router_id = router_id
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
        return build

    def get_port_id(self, build):
        port_id = ""
        for port in self.neutron.list_ports()['ports']:
            if port['device_id'] == build.server.id:
                return port['id']
        return port_id

    def failover(self, node_up, node_down):
        """
        Move vips on to first controller and fail it
        """
        logger.info("Failing {0}...".format(node_down.name))
        logger.debug('Sleeping for 10 seconds...')
        sleep(10)
        self.move_vips_from(node_up)
        logger.debug('Powering down node')
        self.fail_node(node_down)

    def wait_service(self, service, node, retry=10):
        service_up = False
        while not service_up:
            logger.debug("Checking {0} on {1}".format(service, node.name))
            service_up = node.run_cmd("pgrep -fl {0}".format(
                                      service))['return'].rstrip()
            if not service_up:
                logger.debug("{0} is not running on {1}".format(
                                  service, node.name))
                retry -= 1
                if retry == 0:
                    logger.warning("Manually starting {0}".format(
                                        service))
                    node.run_cmd("service {0} start".format(service))
                sleep(1)
        logger.debug("{0} is up on {1}!".format(service, node.name))

    def verify(self, builds, node_up, node_down=None):
        """
        Verifies state persistence
        """
        logger.info("Verifying cluster integrity...")

        # Checks if RS Cloud libvirt issue has been resolved
        libvirt = node_up.run_cmd(";".join(["source openrc",
                                  ("nova service-list | awk '{print $2}' "
                                   "| grep 'nova-compute'")]))['return']
        assert "compute" in libvirt, "The compute nodes are not reporting properly!"

        # Check RPCS services (ha_proxy, keepalived, rpc daemon)
        services = ['haproxy', 'keepalived', 'rpcdaemon']
        for service in services:
            self.wait_service(service, node_up)

        if node_down:
            for service in services:
                self.wait_service(service, node_down)

        # Check that the VIPS moved over to node_up
        logger.debug("Checking for vips on {0}".format(node_up.name))
        exec_vips = node_up.run_cmd("ip netns exec vips ip a")['return']
        exec_vips_down = " "
        if node_down:
            logger.debug("Checking for vips on {0}".format(
                              node_down.name))
            exec_vips_down = node_down.run_cmd("ip netns exec vips ip a")[
                'return']

        vips = self.deployment.environment.override_attributes[
            'vips']['config'].keys()
        for vip in vips:
            logger.debug("VIP: {0}".format(vip))
        for vip in vips:
            logger.debug(("Verifying that {0} is in the vips "
                               "namespace...").format(vip))
            # Checks if the vips are absent from both controllers
            while (vip not in exec_vips) and (vip not in exec_vips_down):
                logger.debug(("{0} is not found in the vips "
                                   "namespace").format(vip))
                sleep(1)
                exec_vips = node_up.run_cmd("ip netns exec vips "
                                            "ip a")['return']
                if node_down:
                    exec_vips_down = node_down.run_cmd("ip netns exec vips "
                                                       "ip a")['return']
            # Verifies that the vips do not reside on both servers
            if (vip in exec_vips) and (vip in exec_vips_down):
                assert vip not in exec_vips, ("{0} vip found on both "
                                              "controllers").format(vip)
            # Checks for the vips on node_up controller
            elif vip in exec_vips:
                logger.debug("{0} vip found in {1}...".format(
                                  vip, node_up.name))
            # Checks for the vips on the node_down controller
            else:
                logger.debug("{0} vip found on {1}...".format(
                                  vip, node_down.name))

###########################################################################
#       IP NETNS NEEDS TO CONTAIN NEUTRON NET-LIST?
#       ip_netns_value = node_up.run_cmd("ip netns")['return'].rstrip()
###########################################################################

        # Check networks rescheduled
        for build in builds:
            logger.debug("Checking DHCP on {0}".format(build.name))
            self.wait_dhcp_agent_alive(build.network_id)
#-----------------------------------------------------------------
        # Check connectivity to builds
        #print "Checking connectivity to builds..."
        #for build in builds:
        #    while not self.is_online(build.ipaddress):
        #        logger.debug(("Build {0} with IP {1} IS NOT "
        #                           "responding...").format(build.name,
        #                                                   build.ipaddress)
        #    logger.debug("Build {0} with IP {1} IS responding...".
        #                      format(build.name, build.ipaddress)
#-----------------------------------------------------------------

###########################################################################
        # Check MySQL replication isn't broken and Controller2 is master.
        #CAM
###########################################################################

        # Check rabbitmq
        self.test_rabbit_status()

###########################################################################
        # Check if all the configured Openstack Services are functional.
        # Run tempest based on the features enabled.
        #SELECTIVE TEMPEST RUN
###########################################################################

###########################################################################
#       NEED TO DETERMINE NUMBER OF COMPUTE NODES TO VERIFY!!!
###########################################################################
        nova_status = "down"
        while nova_status == "down":
            logger.debug("Checking if nova is up on compute")
            nova_status = node_up.run_cmd(";".join(["source openrc", "nova "
                                                    "service-list | grep "
                                                    "compute | awk '{print "
                                                    "$10}'"
                                                    ""]))['return'].rstrip()
            logger.debug("Nova has a state of {0}".format(nova_status))

    def wait_dhcp_agent_alive(self, net, wait=240):
        """
        Waits until dhcp agent for net is alive
        """
        count = 0
        dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(net)
        in_time = lambda x: wait > x

        while not dhcp_status['agents'] and in_time(count):
            logger.debug("Waiting for agents to populate".format(
                dhcp_status))
            sleep(1)
            count += 1
            dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(net)
        assert in_time(count), "Agents failed to populate in time"

        while not dhcp_status['agents'][0]['alive'] and in_time(count):
            logger.debug("Waiting for agents to be rise".format(
                dhcp_status))
            sleep(1)
            count += 1
            dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(net)
        assert in_time(count), "Agents failed to rise in time"
        logger.debug("DHCP is alive")

    def failback(self, node_down):
        """
        Unfails a node
        """
        logger.info("Performing Failback operation...")
        node_down.power_on()
        count = 1
        while not self.is_online(node_down.ipaddress):
            logger.debug("Waiting for {0} to boot - s:{1}".format(
                              node_down.name, count))
            sleep(1)
            count += 1

    def run_tests(self):
        """
        Run ha tests
        """
        #-------------------#
        # Preparation Begin #
        #-------------------#
        #branch = TempestQuantum.tempest_branch(self.deployment.branch)
        #if "grizzly" in branch:
        #    tempest = TempestQuantum(self.deployment)
        #else:
        #    tempest = TempestNeutron(self.deployment)
        images = self.nova.images.list()
        server_image = next(i for i in images if "cirros" in i.name)
        flavors = self.nova.flavors.list()
        server_flavor = next(f for f in flavors if "tiny" in f.name)
        #-----------------#
        # Preparation End #
        #-----------------#

        iterations = self.iterations
        build_stages = 4
        verify_stages = 5
        failover_stages = 2
        failback_stages = 2

        bars = [{'name': 'Iteration', 'current': self.current_iteration,
                 'total': iterations},
                {'name': 'Build', 'current': 0, 'total': build_stages},
                {'name': 'Verify', 'current': 0, 'total': verify_stages},
                {'name': 'Failover', 'current': 0, 'total': failover_stages},
                {'name': 'Failback', 'current': 0, 'total': failback_stages}]
        progress = Progress(bars)

        builds = []

        node_up = self.controller1
        node_down = self.controller2

        stage = 0
        while stage < 3:
            #os.system('clear')
            progress.display("Verify")
            self.verify(builds, node_up, node_down)
            progress.advance("Verify")
            #os.system('clear')

            progress.display("Build")
            build = self.build("testbuild{0}".format(stage),
                               server_image, server_flavor,
                               "testnetwork{0}".format(stage),
                               "testsubnet{0}".format(stage),
                               "testrouter{0}".format(stage),
                               "172.32.{0}.0/24".format(stage))
            stage += 1
            builds.append(build)
            progress.advance("Build")

            progress.display("Failover")
            self.failover(node_up, node_down)
            progress.advance("Failover")

            progress.display("Verify")
            self.verify(builds, node_up)
            progress.advance("Verify")

            progress.display("Build")
            build = self.build("testbuild{0}".format(stage),
                               server_image, server_flavor,
                               "testnetwork{0}".format(stage),
                               "testsubnet{0}".format(stage),
                               "testrouter{0}".format(stage),
                               "172.32.{0}.0/24".format(stage))
            stage += 1
            builds.append(build)
            progress.advance("Build")

            progress.display("Failback")
            self.failback(node_down)
            progress.advance("Failback")

            node_temp = node_up
            node_up = node_down
            node_down = node_temp

        progress.display("Verify")
        self.verify(builds, node_up, node_down)
        progress.advance("Verify")

        progress.display("Iteration")

        for build in builds:
            build.destroy(self.nova, self.neutron)

        progress.advance("Iteration")
        progress.display("Iteration")
        self.current_iteration += 1
        #tempest.test_node = node_up
        #tempest.test()

    def test_rabbit_status(self):
        """
        Assures rabbit is alive
        """
        status = False
        while not status:
            logger.debug("Testing if RabbitMQ is alive")
            try:
                status = self.rabbit.is_alive()
                logger.debug("RabbitMQ is alive")
            except:
                status = False

    def test_list_queues(self):
        """
        Assures rabbit can list queues
        """
        queues = self.rabbit.list_queues()
        assert queues is not None, "queues empty"

    def collect_results(self):
        """
        Collect report and merge tests
        """
        xunit_merge()

    def test(self, iterations, provider_net):
        self.provider_net = provider_net
        self.iterations = iterations
        self.run_tests()
        self.collect_results()


class Progress(object):
    def __init__(self, bars):
        self.bars = bars

    def advance(self, bar_name):
        logger.debug("Advancing {0}...".format(bar_name))
        for bar in self.bars:
            if bar['name'] == bar_name:
                bar['current'] += 1

    def print_bar(self, bar, size, curr):
        logger.debug("Printing bar {0}...".format(bar['name']))
        sys.stdout.write("   {0}:[".format(bar['name']))
        self.set_color("bold")
        self.set_color("blue")
        complete = (float(bar['current']) / int(bar['total'])) * size
        for i in range(int(complete)):
            sys.stdout.write("|")

        self.set_color("yellow")
        self.set_color("blink")
        work_on = 0
        if curr == 1:
            work_on = (float(1) / int(bar['total'])) * size
            for i in range(int(work_on)):
                if (size - complete) > 0:
                    sys.stdout.write("|")

        self.set_color("default")
        self.set_color("gray")
        remain = (size - int(complete) - int(work_on))
        for i in range(remain):
            sys.stdout.write("|")
        self.set_color("default")
        sys.stdout.write("]   ")

    def set_color(self, style):
        logger.debug("Changing output color to {0}...".format(style))
        if style == "default":
            sys.stdout.write("\033[0m")
        elif style == "bold":
            sys.stdout.write("\033[1m")
        elif style == "blue":
            sys.stdout.write("\033[34m")
        elif style == "yellow":
            sys.stdout.write("\033[33m")
        elif style == "gray":
            sys.stdout.write("\033[90m")
        elif style == "blink":
            sys.stdout.write("\033[5m")

    def display(self, current_bar_name):
        logger.debug('Flushing print buffer for status bar...')
        #for i in range(210):
        #    sys.stdout.write("\b")

        os.system('clear')
        for bar in self.bars:
            if bar['name'] == "Iteration":
                self.print_bar(bar, 10, 1)
            elif bar['name'] == current_bar_name:
                self.print_bar(bar, 10, 1)
            else:
                self.print_bar(bar, 10, 0)
        sys.stdout.flush()
