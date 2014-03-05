import socket
from time import sleep
from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client

from monster import util
from monster.util import xunit_merge
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum
from monster.tests.test import Test


class Creds(object):

    def __init__(self, user, password, url):
        self.user = user
        self.password = password
        self.url = url

class Build(object):

    def __init__(self, server, network_id, subnet_id):
        self.server = server
        self.network_id = network_id
        self.subnet_id = subnet_id

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
        keystone = deployment.environment.override_attributes['keystone']
        user = keystone['admin_user']
        users = keystone['users']
        password = users[user]['password']
        url = self.controller1['keystone']['adminURL']
        creds = Creds(user, password, url)
        return creds

    def instance_cmd(self, server_id, net_id, cmd):
        namespace = "qdhcpd-{0}".format(net_id)
        server = self.nova.servers.get(server_id)
        server_ip = server['server']['ipaddress']
        icmd = ("ip netns exec {0} bash; "
                "ssh -o UseprKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no "
                "-i ~/.ssh/testkey {1}; "
                "{2}").format(namespace, server_ip, cmd)
        server.run_cmd(icmd)

    def get_images(self):
        image_ids = (i.id for i in self.nova.images.list())

        try:
            image_id1 = next(image_ids)
        except StopIteration:
            # No images
            exit(1)
        try:
            image_id2 = next(image_ids)
        except StopIteration:
            # Only one image
            image_id2 = image_id1
        return (image_id1, image_id2)

    def create_network(self, network_name):
        new_net = {"network": {"name": network_name, "shared": True}}
        net = self.neutron.create_network(new_net)
        return net['network']['id']

    def create_subnet(self, subnet_name, network_id, subnet_cidr):
        new_subnet = {"subnet": {
            "name": subnet_name, "network_id": network_id,
            "cidr": subnet_cidr, "ip_version": "4"}}
        subnet = self.neutron.create_subnet(new_subnet)
        return subnet['subnet']['id']

    def keepalived_fail(self, node):
        node.run_cmd("service keepalived stop")

    def keepalived_restore(self, node):
        node.run_cmd("service keepalived start")

    def move_vips_from(self, node_up):
        self.keepalived_fail(node_up)
        self.keepalived_restore(node_up)
        sleep(10) # NEED TO WAIT UNTIL node_down PICKS UP VIPS!!!!!!!!

    def fail_node(self, node):
        node.power_off()

    def prepare(self):
        print "Placeholder for prepare()"

    def is_online(self, node):
        ip = node.ipaddress
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.settimeout(2)
            s.connect((ip, 22))
            s.close()
        except socket.error as e:
            return False
        return True

    def build(self, server_name, server_image, server_flavor, network_name, subnet_name, cidr):
        print "\033[1;44mACTION: Build\033[1;m"
        print "\033[1;44m{0}\033[1;m".format(server_name)
        print "\033[1;44m{0}\033[1;m".format(server_image)
        print "\033[1;44m{0}\033[1;m".format(server_flavor)
        print "\033[1;44m{0}\033[1;m".format(network_name)
        print "\033[1;44m{0}\033[1;m".format(subnet_name)
        print "\033[1;44m{0}\033[1;m".format(cidr)
        network_id = self.create_network(network_name)
        print "\033[1;44mNETWORK ID!!!: {0}\033[1;m".format(network_id)
        subnet_id = self.create_subnet(subnet_name, network_id, cidr)
        print "\033[1;44m{0}\033[1;m".format(subnet_id)
        networks = [{"net-id": network_id}]
        print "\033[1;44m{0}\033[1;m".format(networks)
        server = self.nova.servers.create(server_name, server_image,
                                          server_flavor, nics=networks)
        print "\033[1;44m{0}\033[1;m".format(server)
        build_status = "BUILD"
        while build_status == "BUILD":
            build_status = self.nova.servers.get(server.id).status
        print "BUILD STATUS: {0}".format(build_status)
        if build_status == "ERROR":
            print "\033[1;41mBuild FAILED TO INITIALIZE!\033[1;m"
            #pass
        build = Build(server, network_id, subnet_id)
        return build

    def failover(self, node_up, node_down):
        """
        Move vips on to first controller and fail it
        """
        print "\033[1;44mACTION: Failover\033[1;m"
        sleep(60)
        self.move_vips_from(node_up)
        self.fail_node(node_down)
        sleep(30)
    def verify(self, build, node_up, node_down=None):
        print "\033[1;44mACTION: Verify\033[1;m"
        rabbitmq_status = False
        while not rabbitmq_status and node_down:
            rabbitmq_status = node_down.run_cmd("pgrep -fl rabbitmq-server")

        # Check RPCS services (ha_proxy, keepalived, rpc daemon) are functional.
        haproxy = node_up.run_cmd("pgrep -fl haproxy")['return'].rstrip()
        keepalived = node_up.run_cmd("pgrep -fl keepalived")['return'].rstrip()
        rpcdaemon = node_up.run_cmd("pgrep -fl rpcdaemon")['return'].rstrip()

        while not haproxy:
            print "Checking for haproxy status on {0}".format(node_up.name)
            sleep(10)
            haproxy = node_up.run_cmd("pgrep -fl haproxy")['return'].rstrip()
        print "haproxy is up on {0}!".format(node_up.name)
        while not keepalived:
            print "Checking for keepalived status on {0}".format(node_up.name)
            sleep(10)
            keepalived = node_up.run_cmd("pgrep -fl keepalived")['return'].rstrip()
        print "keepalived is up on {0}!".format(node_up.name)
        while not rpcdaemon:
            print "Checkiong for rpcdaemon status on {0}".format(node_up.name)
            sleep(10)
            rpcdaemon = node_up.run_cmd("pgrep -fl rpcdaemon")['return'].rstrip()
        print "rpcdaemon is up on {0}!".format(node_up.name)

        if node_down:
            haproxy = node_down.run_cmd("pgrep -fl haproxy")['return'].rstrip()
            while not haproxy:
                print "Checking for haproxy status on {0}".format(node_down.name)
                sleep(10)
                haproxy = node_down.run_cmd("pgrep -fl haproxy")['return'].rstrip()
            print "haproxy is up on {0}!".format(node_down.name)
            keepalived = node_down.run_cmd("pgrep -fl keepalived")['return'].rstrip()
            while not keepalived:
                print "Checking for keepalived status on {0}".format(node_down.name)
                sleep(10)
                keepalived = node_down.run_cmd("pgrep -fl keepalived")['return'].rstrip()
            print "keepalived is up on {0}!".format(node_down.name)
            rpcdaemon = node_down.run_cmd("pgrep -fl rpcdaemon")['return'].rstrip()
            while not rpcdaemon:
                print "Checkiong for rpcdaemon status on {0}".format(node_down.name)
                sleep(10)
                rpcdaemon = node_down.run_cmd("pgrep -fl rpcdaemon")['return'].rstrip()
            print "rpcdaemon is up on {0}!".format(node_down.name)

        # Check that the VIPS moved over to node_up
        exec_vips = node_up.run_cmd("ip netns exec vips ip a")['return']
        exec_vips_down = " "
        if node_down:
            exec_vips_down = node_down.run_cmd("ip netns exec vips ip a")['return']
        #print "RETVALUE ip netns exec vips ip a: {0}".format(exec_vips)

        vips = self.deployment.environment.override_attributes['vips']['config'].keys()
        for vip in vips:
            print "VIP: {0}".format(vip)
        for vip in vips:
            print "Verifying that {0} is in the vips namespace...".format(vip)
            # Checks if the vips are absent from both controllers
            if (vip not in exec_vips) and (vip not in exec_vips_down):
                print "{0} is not found in the vips namespace!!!".format(vip)
            # Verifies that the vips do not reside on both servers simultaneously
            elif (vip in exec_vips) and (vip in exec_vips_down):
                print "{0} has been found in the vips namespace of both controllers!!!".format(vip)
            # Checks for the vips on node_up controller
            elif (vip in exec_vips):
                print "{0} has been found in the vips namespace of {1}...".format(vip, node_up.name)
            # Checks for the vips on the node_down controller (must have been brought back up)
            else:
                print "{0} has been found in the vips namespace of {1}...".format(vip, node_down.name)

        #IP NETNS NEEDS TO CONTAIN NEUTRON NET-LIST

        ip_netns_value = node_up.run_cmd("ip netns")['return'].rstrip()
        #print "RETVALUE ip netns: {0}".format(ip_netns_value)
        current_host = node_up.run_cmd("hostname")['return'].rstrip()
        print "hostname: {0}".format(current_host)
        
        # Check that the RPC Daemon rescheduled the DHCP/L3 agents to node_up and they are functioning.
        dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(build.network_id)
        util.logger.debug("DHCP_STATUS: {0}".format(dhcp_status))
        #print "DHCP STATUS!!!!!!!!: {0}".format(dhcp_status)
        while not dhcp_status['agents']:
            print "BUILD.Network_ID: {0}".format(build.network_id)
            print "DHCP Status: {0}".format(dhcp_status)
            print "DHCP down. Waiting 5 seconds..."
            sleep(5)
            dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(build.network_id)
        assert dhcp_status['agents'][0]['admin_state_up'],\
            "dhcp is NOT working properly"
        assert dhcp_status['agents'][0]['alive'],\
            "dhcp is NOT working properly"
        print "DHCP status checked..."

        # Check MySQL replication isn't broken and Controller2 is master.
        #CAMERON

        # Check VIP bound RabbitMQ queues have properly reconnected and are functional.
        #CAMERON


        # Check if all the configured Openstack Services are functional.
        # Run tempest based on the features enabled.
        #SELECTIVE TEMPEST RUN

    def failback(self, node_down):
        print "\033[1;44mACTION: Failback\033[1;m"
        node_down.power_on()
        while not self.is_online(node_down):
            print "Waiting for {0} to boot...".format(node_down.name)
            sleep(10)
        sleep(90)

    def destroy(self, build1, build2, build3, build4):
        print "Deleting server..."
        self.nova.servers.delete(build1.server)
        print "Deleting server..."
        self.nova.servers.delete(build2.server)
        print "Deleting server..."
        self.nova.servers.delete(build3.server)
        print "Deleting server..."
        self.nova.servers.delete(build4.server)
        sleep(5)
        print "Deleting subnet..."
        self.neutron.delete_subnet(build1.subnet_id)
        print "Deleting network..."
        self.neutron.delete_network(build1.network_id)
        print "Deleting subnet..."
        self.neutron.delete_subnet(build2.subnet_id)
        print "Deleting network..."
        self.neutron.delete_network(build2.network_id)
        print "Deleting subnet..."
        self.neutron.delete_subnet(build3.subnet_id)
        print "Deleting network..."
        self.neutron.delete_network(build3.network_id)
        print "Deleting subnet..."
        self.neutron.delete_subnet(build4.subnet_id)
        print "Deleting network..."
        self.neutron.delete_network(build4.network_id)
        
    def run_tests(self):
        """
        Run tempest on second controller
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

        node1 = self.controller1
        node2 = self.controller2
        node_up = self.controller1
        node_down = self.controller2
        run = 0
        build1 = self.build("testbuild{0}".format(run),
                       server_image, server_flavor,
                       "testnetwork{0}".format(run),
                       "testsubnet{0}".format(run),
                       "172.32.{0}.0/24".format(run))
        self.verify(build1, node_up, node_down)
        self.failover(node_up, node_down)
        self.verify(build1, node_up)
        run = 1
        build2 = self.build("testbuild{0}".format(run),
                       server_image, server_flavor,
                       "testnetwork{0}".format(run),
                       "testsubnet{0}".format(run),
                       "172.32.{0}.0/24".format(run))
        self.failback(node_down)
        self.verify(build2, node_up, node_down) #NEED TO FIGURE OUT WHICH NODE TO PASS

        node_up = self.controller2
        node_down = self.controller1
        run = 2
        build3 = self.build("testbuild{0}".format(run),
                       server_image, server_flavor,
                       "testnetwork{0}".format(run),
                       "testsubnet{0}".format(run),
                       "172.32.{0}.0/24".format(run))
        self.failover(node_up, node_down)
        self.verify(build3, node_up)
        run = 3
        build4 = self.build("testbuild{0}".format(run),
                       server_image, server_flavor,
                       "testnetwork{0}".format(run),
                       "testsubnet{0}".format(run),
                       "172.32.{0}.0/24".format(run))
        self.failback(node_down)
        self.verify(build4, node_up, node_down) #NEED TO FIGURE OUT WHICH NODE TO PASS

        self.destroy(build1, build2, build3, build4)
        #tempest.test_node = node_up
        #tempest.test()

    def test_rabbit_status(self):
        status = self.rabbit.is_alive()
        assert status is True, "rabbit is dead"

    def test_list_queues(self):
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
