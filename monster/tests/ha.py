from time import sleep
import json
from subprocess import check_call
from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client

from monster.util import xunit_merge
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum
from monster.tests.test import Test


class Creds(object):

    def __init__(self, user, password, url):
        self.user = user
        self.password = password
        self.url = url


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
                "ssh -o UseprKnownHostsFile=/dev/null -o StrictHostKeyChecking=no -i ~/.ssh/testkey {1}; "
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

    def move_vips_from(self, node):
        self.keepalived_fail(node)
        self.keepalived_restore(node)
        #sleep(10)               # wait for node to be ready

    def fail_node(self, node):
        node.power_off()

    def prepare(self):
        """
        Move vips on to first controller and fail it
        """
        self.move_vips_from(self.controller2)

        #self.fail_node(self.controller1)
        #sleep(60)

    def run_tests(self):
        """
        Run tempest on second controller
        """
        branch = TempestQuantum.tempest_branch(self.deployment.branch)
        if "grizzly" in branch:
            tempest = TempestQuantum(self.deployment)
        else:
            tempest = TempestNeutron(self.deployment)
        tempest.test_node = self.controller2

        netns_value = tempest.test_node.run_cmd("ip netns exec vips ip a")
        netns_value = netns_value['return']
        #print "RETVALUE ip netns exec vips ip a: {0}".format(netns_value)


        server_name = "testbuild"
        server_image = self.nova.images.list()[1] # [0] precise [1] cirros
        server_flavor = self.nova.flavors.list()[0] # [0] m1.tiny[1] m1. small [2] m1.medium [3] m1.large [4]m1.xlarge
        network_name = "testnetwork"
        subnet_name = "testsubnet"
        network_id = self.create_network(network_name)
        subnet_id = self.create_subnet(subnet_name, network_id,
                                       "172.32.0.0/24")

        networks = [{"net-id": network_id}]

        server = self.nova.servers.create(server_name, server_image,
                                 server_flavor, nics=networks)
        build_status = "BUILD"
        while build_status == "BUILD":
            build_status = self.nova.servers.list()[0].status

        if build_status == "ERROR":
            print "\033[1;41mBuild FAILED TO INITIALIZE!\033[1;m"
            #pass

        ip_netns_value = tempest.test_node.run_cmd("ip netns")
        ip_netns_value = ip_netns_value['return'].rstrip()
        #print "RETVALUE ip netns: {0}".format(ip_netns_value)

        current_host = tempest.test_node.run_cmd("hostname")
        current_host = current_host['return'].rstrip()
        print "hostname: {0}".format(current_host)


        dhcp_status = self.neutron.list_dhcp_agent_hosting_networks(network_id)
        #print "DHCP STATUS!!!!!!!!: {0}".format(dhcp_status)
        assert (dhcp_status['agents'][0]['admin_state_up'] and
                dhcp_status['agents'][0]['alive']),\
            "dhcp is NOT working properly"

        print "Deleting server..."
        self.nova.servers.delete(server)
        sleep(5)
        print "Deleting subnet..."
        self.neutron.delete_subnet(subnet_id)
        print "Deleting network..."
        self.neutron.delete_network(network_id)

        #tempest.test()

        self.controller1.power_on()
        sleep(5)

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
        self.prepare()
        self.run_tests()
        self.collect_results()
