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
from monster.util import xunit_merge
from monster.tests.test import Test


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
        #from IPython import embed
        #embed()
        util.logger.debug("Deleting floating IP...")
        deleted = False
        while not deleted:
            try:
                neutron.delete_floatingip(self.ip_info['id'])
                deleted = True
            except:
                deleted = False

        util.logger.debug("Deleting server...")
        deleted = False
        while not deleted:
            try:
                nova.servers.delete(self.server)
                deleted = True
            except:
                deleted = False

        util.logger.debug("Deleting router interface...")
        deleted = False
        while not deleted:
            try:
                neutron.remove_interface_router(self.router_id, {"subnet_id": self.subnet_id})
                deleted = True
            except:
                deleted = False

        util.logger.debug("Deleting router...")
        deleted = False
        while not deleted:
            try:
                neutron.delete_router(self.router_id)
                deleted = True
            except:
                deleted = False

        util.logger.debug("Deleting subnet...")
        deleted = False
        while not deleted:
            try:
                neutron.delete_subnet(self.subnet_id)
                deleted = True
            except:
                deleted = False

        util.logger.debug("Deleting network...")
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

    def gather_creds(self, deployment):
        """
        Creates cred object based off deployment
        """
        keystone = deployment.environment.override_attributes['keystone']
        user = keystone['admin_user']
        util.logger.debug("User: {0}".format(user))
        users = keystone['users']
        password = users[user]['password']
        util.logger.debug("Pass: {0}".format(password))
        url = self.controller1['keystone']['adminURL']
        util.logger.debug("URL: {0}".format(url))
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
        new_router = {"router":{
                      "name":router_name,
                      "admin_state_up":admin_state_up}}
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
        self.keepalived_fail(node_up)
        sleep(5)
        self.keepalived_restore(node_up)
        # NEED TO WAIT UNTIL node_down PICKS UP VIPS!!!!!!!!
        sleep(10)

    def fail_node(self, node):
        """
        Failover a node
        """
        node.power_off()

    def prepare(self):
        """
        Prepares to run tests
        """

        util.logger.debug("Placeholder for prepare()")

    def is_online(self, ip):
        """
        Returns true if a connection can be made with ssh
        """
        util.logger.debug("IP ADDRESS: {0}".format(ip))
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(2)
            s.connect((ip, 22))
            s.close()
        except socket.error:
            return False
        return True

    def build(self, server_name, server_image, server_flavor, network_name,
              subnet_name, router_name, cidr):
        """
        Builds state in OpenStack (net, server)
        """
        util.logger.debug("\033[1;44mACTION: Build\033[0m")
        util.logger.debug("\033[1;44mBuild Name: {0}\033[0m".format(
                          server_name))

        network_id = self.create_network(network_name)
        util.logger.debug("\033[1;44mNetwork ID: {0}\033[0m".format(
                          network_id))

        subnet_id = self.create_subnet(subnet_name, network_id, cidr)
        util.logger.debug("\033[1;44mSubnet ID: {0}\033[0m".format(
                          subnet_id))

        router_id = self.create_router(router_name)
        util.logger.debug("\033[1;44mRouter ID: {0}\033[0m".format(
                          router_id))

        iface_port = self.add_router_interface(router_id, subnet_id)
        util.logger.debug("\033[1;44mInterface Port: {0}\033[0m".format(
                          iface_port))
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
        provider_net_id = self.provider_net

        self.neutron.add_gateway_router(router_id, body={"network_id":provider_net_id})
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------

        networks = [{"net-id": network_id}]
        util.logger.debug("Building server with above parameters...")
        server = False
        while not server:
            try:
                util.logger.debug("Attempting server creation...")
                server = self.nova.servers.create(server_name, server_image,
                                                  server_flavor, nics=networks)
                util.logger.debug("Server creation command executed!")
            except:
                server = False
                util.logger.debug("Server creation command failed epicly!")
                util.logger.debug("The epicness of its failure was truly a "
                                  "sight to behold...")
                sleep(1)

        util.logger.debug("Executed build command...")
        build_status = "BUILD"
        #from IPython import embed
        #embed()
        while build_status == "BUILD":
            build_status = self.nova.servers.get(server.id).status
        if build_status == "ERROR":
            util.logger.error("\033[1;41mBuild failed to initialize!\033[0m")
            assert (build_status == "ERROR"), "Build failed to initialize!"
            #pass
        else:
            util.logger.debug("Build status: {0}".format(build_status))
        build = Build(server, network_id, subnet_id, server_name,
                      server_image, server_flavor)
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
        port_id = next(port['id'] for port in self.neutron.list_ports()['ports'] if port['device_id'] == build.server.id)
        floating_ip = self.neutron.create_floatingip({"floatingip":{"floating_network_id":provider_net_id, "port_id":port_id}})
        build.ip_info = floating_ip['floatingip']
        build.router_id = router_id
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
        return build

    def failover(self, node_up, node_down):
        """
        Move vips on to first controller and fail it
        """
        util.logger.debug("\033[1;44mACTION: Failover\033[0m")
        util.logger.debug("Sleeping for 10 seconds...")
        sleep(10)
        self.move_vips_from(node_up)
        self.fail_node(node_down)

    def verify(self, builds, node_up, node_down=None):
        """
        Verifies state persistence
        """
        util.logger.debug("\033[1;44mACTION: Verify\033[0m")
        # Check RPCS services (ha_proxy, keepalived, rpc daemon)
        haproxy = node_up.run_cmd("pgrep -fl haproxy")['return'].rstrip()
        while not haproxy:
            util.logger.debug("Checking for haproxy status on {0}".format(node_up.name))
            sleep(1)
            haproxy = node_up.run_cmd("pgrep -fl haproxy")['return'].rstrip()
        util.logger.debug("haproxy is up on {0}!".format(node_up.name))

        keepalived = node_up.run_cmd("pgrep -fl keepalived")['return'].rstrip()
        while not keepalived:
            util.logger.debug("Checking for keepalived status on {0}".format(node_up.name))
            sleep(1)
            keepalived = node_up.run_cmd("pgrep -fl keepalived")[
                'return'].rstrip()
        util.logger.debug("keepalived is up on {0}!".format(node_up.name))

        rpcdaemon = node_up.run_cmd("pgrep -fl rpcdaemon")['return'].rstrip()
        retry = 10
        while not rpcdaemon:
            util.logger.debug("Checking for rpcdaemon status on {0}".format(node_up.name))
            sleep(1)
            retry -= 1
            if retry == 0:
                node_up.run_cmd("service rpcdaemon start")
                sleep(1)
                util.logger.debug("\033[1;41mSTARTING RPCDAEMON!\033[0m")
            rpcdaemon = node_up.run_cmd("pgrep -fl rpcdaemon")[
                'return'].rstrip()
        util.logger.debug("rpcdaemon is up on {0}!".format(node_up.name))

        if node_down:
            haproxy = node_down.run_cmd("pgrep -fl haproxy")['return'].rstrip()
            while not haproxy:
                util.logger.debug("Checking for haproxy status on {0}".format(
                    node_down.name))
                sleep(1)
                haproxy = node_down.run_cmd("pgrep -fl haproxy")[
                    'return'].rstrip()
            util.logger.debug("haproxy is up on {0}!".format(node_down.name))

            keepalived = node_down.run_cmd("pgrep -fl keepalived")[
                'return'].rstrip()
            while not keepalived:
                util.logger.debug("Checking for keepalived status on {0}".format(
                    node_down.name))
                sleep(1)
                keepalived = node_down.run_cmd("pgrep -fl keepalived")[
                    'return'].rstrip()
            util.logger.debug("keepalived is up on {0}!".format(node_down.name))

            rpcdaemon = node_down.run_cmd("pgrep -fl rpcdaemon")[
                'return'].rstrip()
            retry = 10
            while not rpcdaemon:
                util.logger.debug("Checking for rpcdaemon status on {0}".format(
                    node_down.name))
                sleep(1)
                retry -= 1
                if retry == 0:
                    node_down.run_cmd("service rpcdaemon start")
                    sleep(1)
                    util.logger.debug("\033[1;41mSTARTING RPCDAEMON!\033[0m")
                rpcdaemon = node_down.run_cmd("pgrep -fl rpcdaemon")[
                    'return'].rstrip()
            util.logger.debug("rpcdaemon is up on {0}!".format(node_down.name))

        # Check that the VIPS moved over to node_up
        exec_vips = node_up.run_cmd("ip netns exec vips ip a")['return']
        exec_vips_down = " "
        if node_down:
            exec_vips_down = node_down.run_cmd("ip netns exec vips ip a")[
                'return']
        #print "RETVALUE ip netns exec vips ip a: {0}".format(exec_vips)

        vips = self.deployment.environment.override_attributes[
            'vips']['config'].keys()
        for vip in vips:
            util.logger.debug("VIP: {0}".format(vip))
        for vip in vips:
            util.logger.debug("Verifying that {0} is in the vips namespace...".format(vip))
            # Checks if the vips are absent from both controllers
            while (vip not in exec_vips) and (vip not in exec_vips_down):
                util.logger.debug("{0} is not found in the vips namespace!!!".format(vip))
                sleep(1)
                exec_vips = node_up.run_cmd("ip netns exec vips "
                                            "ip a")['return']
                if node_down:
                    exec_vips_down = node_down.run_cmd("ip netns exec vips "
                                                       "ip a")['return']
            # Verifies that the vips do not reside on both servers
            if (vip in exec_vips) and (vip in exec_vips_down):
                assert vip not in exec_vips, ("{0} vip found on both "
                                              "controllers!!!").format(vip)
            # Checks for the vips on node_up controller
            elif vip in exec_vips:
                util.logger.debug("{0} vip found in {1}...".format(vip, node_up.name))
            # Checks for the vips on the node_down controller
            else:
                util.logger.debug("{0} vip found on {1}...".format(vip, node_down.name))

        #IP NETNS NEEDS TO CONTAIN NEUTRON NET-LIST

        ip_netns_value = node_up.run_cmd("ip netns")['return'].rstrip()
        util.logger.debug("ip netns: {0}".format(ip_netns_value))
        current_host = node_up.run_cmd("hostname")['return'].rstrip()
        util.logger.debug("hostname: {0}".format(current_host))

        # --------------------------------------review
        # Check networks rescheduled
        for build in builds:
            util.logger.debug("\033[1;44mChecking DHCP for build {0}\033[0m".format(
                  build.name))
            self.wait_dhcp_agent_alive(build.network_id)
#-----------------------------------------------------------------
        # Check connectivity to builds
        #print "Checking connectivity to builds..."
        #for build in builds:
        #    while not self.is_online(build.ipaddress):
        #        util.logger.debug("Build {0} with IP {1} IS NOT responding...".format(build.name, build.ipaddress)
        #    util.logger.debug("Build {0} with IP {1} IS responding...".format(build.name, build.ipaddress)
#-----------------------------------------------------------------

        # Check MySQL replication isn't broken and Controller2 is master.
        #CAM

        # Check rabbitmq
        self.test_rabbit_status()

        # Check if all the configured Openstack Services are functional.
        # Run tempest based on the features enabled.
        #SELECTIVE TEMPEST RUN
        nova_status = node_up.run_cmd(";".join(["source openrc",
                                                "nova service-list | grep "
                                                "compute | awk '{print "
                                                "$10}'"]))['return'].rstrip()
        util.logger.debug("NOVA STATUS: {0}".format(nova_status))
        while nova_status == "down":
            util.logger.debug("Waiting for nova to come up on compute...")
            sleep(1)
            nova_status = node_up.run_cmd(";".join(["source openrc", "nova "
                                                    "service-list | grep "
                                                    "compute | awk '{print "
                                                    "$10}'"
                                                    ""]))['return'].rstrip()
            util.logger.debug("NOVA STATUS: {0}".format(nova_status))

    def wait_dhcp_agent_alive(self, net, wait=240):
        """
        Waits until dhcp agent for net is alive
        """
        count = 1
        dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(net)
        in_time = lambda x: wait > x

        while not dhcp_status['agents'] and in_time(count):
            util.logger.debug("waiting for agents to populate:{0}".format(
                dhcp_status))
            sleep(1)
            count += 1
            dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(net)

        assert in_time(count), "agents failed to populate in time"

        while not dhcp_status['agents'][0]['alive'] and in_time(count):
            util.logger.debug("waiting for agents to be alive:{0}".format(
                dhcp_status))
            sleep(1)
            count += 1
            dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(net)

        assert in_time(count), "agents failed to rise in time"
        util.logger.debug("DHCP status checked...")

    def failback(self, node_down):
        """
        Unfails a node
        """
        util.logger.debug("\033[1;44mACTION: Failback\033[1;0m")
        node_down.power_on()
        count = 1
        while not self.is_online(node_down.ipaddress):
            util.logger.debug("Waiting for {0} to boot:{1}".format(
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
        verify_stages = 6
        failover_stages = 2
        failback_stages = 2

        bars = [{'name':'Iteration', 'current':self.current_iteration, 'total':iterations},
                {'name':'Build', 'current':0, 'total':build_stages},
                {'name':'Verify', 'current':0, 'total':verify_stages},
                {'name':'Failover', 'current':0, 'total':failover_stages},
                {'name':'Failback', 'current':0, 'total':failback_stages}]
        progress = Progress(bars)

        node_up = self.controller1
        node_down = self.controller2

        builds = []

        os.system('clear')
        progress.display("Verify")
        self.verify(builds, node_up, node_down)
        progress.advance("Verify")
        os.system('clear')

        run = 0
        progress.display("Build")
        build1 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "testrouter{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build1)
        progress.advance("Build")

        progress.display("Verify")
        self.verify(builds, node_up, node_down)
        progress.advance("Verify")

        progress.display("Failover")
        self.failover(node_up, node_down)
        progress.advance("Failover")

        progress.display("Verify")
        self.verify(builds, node_up)
        progress.advance("Verify")

        run = 1
        progress.display("Build")
        build2 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "testrouter{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build2)
        progress.advance("Build")

        progress.display("Failback")
        self.failback(node_down)
        progress.advance("Failback")

        progress.display("Verify")
        self.verify(builds, node_up, node_down)
        progress.advance("Verify")

        node_up = self.controller2
        node_down = self.controller1

        run = 2
        progress.display("Build")
        build3 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "testrouter{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build3)
        progress.advance("Build")

        progress.display("Failover")
        self.failover(node_up, node_down)
        progress.advance("Failover")

        progress.display("Verify")
        self.verify(builds, node_up)
        progress.advance("Verify")

        run = 3
        progress.display("Build")
        build4 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "testrouter{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build4)
        progress.advance("Build")

        progress.display("Failback")
        self.failback(node_down)
        progress.advance("Failback")

        progress.display("Verify")
        self.verify(builds, node_up, node_down)
        progress.advance("Verify")

        progress.display("Iteration")

        for build in builds:
            build.destroy(self.nova, self.neutron)

        progress.advance("Iteration")

        self.current_iteration += 1
        #tempest.test_node = node_up
        #tempest.test()

    def test_rabbit_status(self):
        """
        Assures rabbit is alive
        """
        util.logger.debug("\033[1;44mTesting if RabbitMQ is alive...\033[0m")
        try:
            status = self.rabbit.is_alive()
        except:
            status = False
        while not status:
            util.logger.debug("Waiting for rabbit resurrection...")
            sleep(1)
            try:
                status = self.rabbit.is_alive()
                util.logger.debug("\033[1;44mRabbitMQ is alive!\033[0m")
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
        for bar in self.bars:
            if bar['name'] == bar_name:
                bar['current'] += 1

    def print_bar(self, bar, size, curr):
        sys.stdout.write("   {0}:[".format(bar['name']))
        self.set_color("bold")
        self.set_color("blue")
        complete = (float(bar['current']) / bar['total']) * size
        for i in range (int(complete)):
            sys.stdout.write("|")
        
        self.set_color("yellow")
        self.set_color("blink")
        work_on = 0
        if curr == 1:
            work_on = (float(1) / bar['total']) * size
            for i in range (int(work_on)):
                if (size - complete) > 0:
                    sys.stdout.write("|")

        self.set_color("default")
        self.set_color("gray")
        remain = (size - int(complete) - int(work_on))
        for i in range (remain):
            sys.stdout.write("|")
        self.set_color("default")
        sys.stdout.write("]   ")


    def set_color(self, style):
        if style == "default": sys.stdout.write("\033[0m")
        elif style == "bold": sys.stdout.write("\033[1m")
        elif style == "blue": sys.stdout.write("\033[34m")
        elif style == "yellow": sys.stdout.write("\033[33m")
        elif style == "gray": sys.stdout.write("\033[90m")
        elif style == "blink": sys.stdout.write("\033[5m")

    def display(self, current_bar_name):
        for i in range (210):
            sys.stdout.write("\b")

        for bar in self.bars:
            if bar['name'] == "Iteration":
                self.print_bar(bar, 40, 1)
            elif bar['name'] == current_bar_name:
                self.print_bar(bar, 20, 1)
            else:
                self.print_bar(bar, 20, 0)

        sys.stdout.flush()
#---------------------------------------
#---------------------------------------
#---------------------------------------
#---------------------------------------
        #sys.stdout.write("\rIterations:[\033[1;34m||||||||||||||\033[5;33m|\033[0;90m|||||\033[0m]")
