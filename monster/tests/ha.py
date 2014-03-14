"""
Module to test High Availability in RPC
"""
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

    def destroy(self, nova, neutron):
        """
        Cleans up build state from OpenStack
        """
        util.logger.debug("Deleting server...")
        deleted = False
        while not deleted:
            try:
                nova.servers.delete(self.server)
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

        controllers = list(self.deployment.search_role("controller"))
        self.controller1 = controllers[0]
        self.controller2 = controllers[1]

        # get creds
        creds = self.gather_creds(deployment)

        # Setup clients
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
        print "User: {0}".format(user)
        users = keystone['users']
        password = users[user]['password']
        print "Pass: {0}".format(password)
        url = self.controller1['keystone']['adminURL']
        print "URL: {0}".format(url)
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

        print "Placeholder for prepare()"

    def is_online(self, node):
        """
        Returns true if a connection can be made with ssh
        """
        ip = ""
        try:
            ip = getattr(node, 'ipaddress')
            print "IP ADDRESS: {0}".format(ip)
        except:
            ip = getattr(node, 'accessIPv4')
            print "ACCESS IPv4: {0}".format(ip)
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
        util.logger.debug("\033[1;44mACTION: Build\033[1;m")
        util.logger.debug("\033[1;44mBuild Name: {0}\033[1;m".format(
                          server_name))

        network_id = self.create_network(network_name)
        util.logger.debug("\033[1;44mNetwork ID: {0}\033[1;m".format(
                          network_id))

        subnet_id = self.create_subnet(subnet_name, network_id, cidr)
        util.logger.debug("\033[1;44mSubnet ID: {0}\033[1;m".format(
                          subnet_id))

        router_id = self.create_router(router_name)
        util.logger.debug("\033[1;44mRouter ID: {0}\033[1;m".format(
                          router_id))

        iface_port = self.add_router_interface(router_id, subnet_id)
        util.logger.debug("\033[1;44mInterface Port: {0}\033[1;m".format(
                          iface_port))
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
        provider_net_id = "0c612a51-a0f7-4a29-9ef1-50375300aedb"

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
        while build_status == "BUILD":
            build_status = self.nova.servers.get(server.id).status
        if build_status == "ERROR":
            util.logger.error("\033[1;41mBuild failed to initialize!\033[1;m")
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
        
#-----------------------------------------------------------------------------
#-----------------------------------------------------------------------------
        return build

    def failover(self, node_up, node_down):
        """
        Move vips on to first controller and fail it
        """
        print "\033[1;44mACTION: Failover\033[1;m"
        print "Sleeping for 10 seconds..."
        sleep(10)
        self.move_vips_from(node_up)
        self.fail_node(node_down)
        #sleep(120)

    def verify(self, builds, node_up, node_down=None):
        """
        Verifies state persistence
        """
        print "\033[1;44mACTION: Verify\033[1;m"
        # Check RPCS services (ha_proxy, keepalived, rpc daemon)
        haproxy = node_up.run_cmd("pgrep -fl haproxy")['return'].rstrip()
        while not haproxy:
            print "Checking for haproxy status on {0}".format(node_up.name)
            sleep(1)
            haproxy = node_up.run_cmd("pgrep -fl haproxy")['return'].rstrip()
        print "haproxy is up on {0}!".format(node_up.name)

        keepalived = node_up.run_cmd("pgrep -fl keepalived")['return'].rstrip()
        while not keepalived:
            print "Checking for keepalived status on {0}".format(node_up.name)
            sleep(1)
            keepalived = node_up.run_cmd("pgrep -fl keepalived")[
                'return'].rstrip()
        print "keepalived is up on {0}!".format(node_up.name)

        rpcdaemon = node_up.run_cmd("pgrep -fl rpcdaemon")['return'].rstrip()
        retry = 10
        while not rpcdaemon:
            print "Checkiong for rpcdaemon status on {0}".format(node_up.name)
            sleep(1)
            retry -= 1
            if retry == 0:
                node_up.run_cmd("service rpcdaemon start")
                sleep(1)
                print "\033[1;41mSTARTING RPCDAEMON!\033[1;m"
            rpcdaemon = node_up.run_cmd("pgrep -fl rpcdaemon")[
                'return'].rstrip()
        print "rpcdaemon is up on {0}!".format(node_up.name)

        if node_down:
            haproxy = node_down.run_cmd("pgrep -fl haproxy")['return'].rstrip()
            while not haproxy:
                print "Checking for haproxy status on {0}".format(
                    node_down.name)
                sleep(1)
                haproxy = node_down.run_cmd("pgrep -fl haproxy")[
                    'return'].rstrip()
            print "haproxy is up on {0}!".format(node_down.name)

            keepalived = node_down.run_cmd("pgrep -fl keepalived")[
                'return'].rstrip()
            while not keepalived:
                print "Checking for keepalived status on {0}".format(
                    node_down.name)
                sleep(1)
                keepalived = node_down.run_cmd("pgrep -fl keepalived")[
                    'return'].rstrip()
            print "keepalived is up on {0}!".format(node_down.name)

            rpcdaemon = node_down.run_cmd("pgrep -fl rpcdaemon")[
                'return'].rstrip()
            retry = 10
            while not rpcdaemon:
                print "Checkiong for rpcdaemon status on {0}".format(
                    node_down.name)
                sleep(1)
                retry -= 1
                if retry == 0:
                    node_down.run_cmd("service rpcdaemon start")
                    sleep(1)
                    print "\033[1;41mSTARTING RPCDAEMON!\033[1;m"
                rpcdaemon = node_down.run_cmd("pgrep -fl rpcdaemon")[
                    'return'].rstrip()
            print "rpcdaemon is up on {0}!".format(node_down.name)

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
            print "VIP: {0}".format(vip)
        for vip in vips:
            print "Verifying that {0} is in the vips namespace...".format(vip)
            # Checks if the vips are absent from both controllers
            while (vip not in exec_vips) and (vip not in exec_vips_down):
                print "{0} is not found in the vips namespace!!!".format(vip)
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
                print "{0} vip found in {1}...".format(vip, node_up.name)
            # Checks for the vips on the node_down controller
            else:
                print "{0} vip found on {1}...".format(vip, node_down.name)

        #IP NETNS NEEDS TO CONTAIN NEUTRON NET-LIST

        ip_netns_value = node_up.run_cmd("ip netns")['return'].rstrip()
        util.logger.debug("ip netns: {0}".format(ip_netns_value))
        current_host = node_up.run_cmd("hostname")['return'].rstrip()
        print "hostname: {0}".format(current_host)

        # --------------------------------------review
        # Check networks rescheduled
        for build in builds:
            print "\033[1;44mChecking DHCP for build {0}\033[1;m".format(
                  build.name)
            self.wait_dhcp_agent_alive(build.network_id)

        # Check connectivity to builds
        print "Checking connectivity to builds..."
        for build in builds:
            from IPython import embed
            embed()
            while not self.is_online(build.server):
                print "Build {0} with IP {1} IS NOT responding...".format(build.name, build.server.accessIPv4)
            print "Build {0} with IP {1} IS responding...".format(build.name, build.server.accessIPv4)

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
        print "NOVA STATUS: {0}".format(nova_status)
        while nova_status == "down":
            print "Waiting for nova to come up on compute..."
            sleep(1)
            nova_status = node_up.run_cmd(";".join(["source openrc", "nova "
                                                    "service-list | grep "
                                                    "compute | awk '{print "
                                                    "$10}'"
                                                    ""]))['return'].rstrip()
            print "NOVA STATUS: {0}".format(nova_status)

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
        print "DHCP status checked..."

    def failback(self, node_down):
        """
        Unfails a node
        """
        print "\033[1;44mACTION: Failback\033[1;m"
        node_down.power_on()
        count = 1
        while not self.is_online(node_down):
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

        node_up = self.controller1
        node_down = self.controller2
        run = 0
        builds = []
        self.verify(builds, node_up, node_down)
        build1 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build1)
        self.verify(builds, node_up, node_down)
        self.failover(node_up, node_down)
        self.verify(builds, node_up)
        run = 1
        build2 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build2)
        self.failback(node_down)
        self.verify(builds, node_up, node_down)

        node_up = self.controller2
        node_down = self.controller1
        run = 2
        build3 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build3)
        self.failover(node_up, node_down)
        self.verify(builds, node_up)
        run = 3
        build4 = self.build("testbuild{0}".format(run),
                            server_image, server_flavor,
                            "testnetwork{0}".format(run),
                            "testsubnet{0}".format(run),
                            "172.32.{0}.0/24".format(run))
        builds.append(build4)
        self.failback(node_down)
        self.verify(builds, node_up, node_down)
        for build in builds:
            build.destroy(self.nova, self.neutron)

        #tempest.test_node = node_up
        #tempest.test()

    def test_rabbit_status(self):
        """
        Assures rabbit is alive
        """
        util.logger.debug("\033[1;44mTesting if RabbitMQ is alive...\033[1;m")
        try:
            status = self.rabbit.is_alive()
        except:
            status = False
        while not status:
            util.logger.debug("Waiting for rabbit resurrection...")
            sleep(1)
            try:
                status = self.rabbit.is_alive()
                util.logger.debug("\033[1;44mRabbitMQ is alive!\033[1;m")
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

    def test(self):
        self.run_tests()
        self.collect_results()
