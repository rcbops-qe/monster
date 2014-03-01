from time import sleep

from monster.util import xunit_merge
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum
from monster.tests.test import Test


class HATest(Test):
    """
    HA Openstack tests
    """

    def __init__(self, deployment):
        super(HATest, self).__init__(deployment)
        controllers = list(self.deployment.search_role("controller"))
        self.controller1 = controllers[0]
        self.controller2 = controllers[1]

    def keepalived_fail(self, node):
        node.run_cmd("service keepalived stop")

    def keepalived_restore(self, node):
        node.run_cmd("service keepalived start")

    def move_vips_from(self, node):
        self.keepalived_fail(node)
        self.keepalived_restore(node)
        sleep(10)               # wait for node to be ready

    def fail_node(self, node):
        node.power_off()
        sleep(60)

    def prepare(self):
        """
        Move vips on to first controller and fail it
        """
        self.move_vips_from(self.controller2)

        #self.fail_node(self.controller1)

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
        print "RETVALUE ip netns exec vips ip a: {0}".format(netns_value)

        srcmd = "source openrc"
        cmd1 = ("neutron net-create testnet | sed '/^| id/!d' | "
                "awk '{{ print $4 }}'")
        neutron_net_create_value = tempest.test_node.run_cmd(";".join([srcmd,
                                                                       cmd1]))
        neutron_net_create_value = neutron_net_create_value['return'].rstrip()
        print ("RETVALUE neutron net-create testnet: "
               "{0}".format(neutron_net_create_value))

        cmd1 = ("neutron subnet-create --name testsubnet {0} 172.32.0.0/24 "
                "--no-gateway | sed '/^| id/!d' | "
                "awk '{{ print $4 }}'".format(neutron_net_create_value))
        neutron_subnet_create_value = tempest.test_node.run_cmd(";".join(
                                                                [srcmd,
                                                                 cmd1]))
        neutron_subnet_create_value = neutron_subnet_create_value['return']
        neutron_subnet_create_value = neutron_subnet_create_value.rstrip()
        print ("RETVALUE neutron subnet-create subtestnet: "
               "{0}".format(neutron_subnet_create_value))

        cmd1 = ("neutron net-list | grep {0} | "
                "grep {1}".format(neutron_net_create_value,
                                  neutron_subnet_create_value))
        neutron_net_list_value = tempest.test_node.run_cmd(";".join([srcmd,
                                                                     cmd1]))
        neutron_net_list_value = neutron_net_list_value['return'].rstrip()
        print "RETVALUE neutron net-list: {0}".format(neutron_net_list_value)
        if not neutron_net_list_value:
            print "Network or Subnet FAILED TO INITIALIZE!"
            #pass

#--nic requires the Value for the field "id" from neutron net-create testnet
        cmd1 = ("nova boot --image cirros-image --flavor 1 --nic net-id={0} "
                "testbuild | sed '/^| id/!d' | "
                "awk '{{ print $4 }}'".format(neutron_net_create_value))
        nova_boot_value = tempest.test_node.run_cmd(";".join([srcmd,
                                                              cmd1]))
        nova_boot_value = nova_boot_value['return'].rstrip()
        print "RETVALUE nova boot: {0}".format(nova_boot_value)

        cmd1 = ("nova list | grep {0} | "
                "awk '{{ print $6 }}'".format(nova_boot_value))
        build_status = "BUILD"
        while build_status == "BUILD":
            build_status = tempest.test_node.run_cmd(";".join([srcmd,
                                                               cmd1]))
            build_status = build_status['return'].rstrip()

        if build_status == "ERROR":
            print "Build FAILED TO INITIALIZE!"
            #pass

        ip_netns_value = tempest.test_node.run_cmd("ip netns")
        ip_netns_value = ip_netns_value['return'].rstrip()
        print "RETVALUE ip netns: {0}".format(ip_netns_value)

        current_host = tempest.test_node.run_cmd("hostname")
        current_host = current_host['return'].rstrip()
        print "RETVALUE hostname: {0}".format(current_host)

        cmd1 = ("neutron dhcp-agent-list-hosting-net testnet | "
                "grep {0} | awk '{{ print $6 }}'".format(current_host))
        neutron_dhcp_value = tempest.test_node.run_cmd(";".join([srcmd,
                                                                 cmd1]))
        neutron_dhcp_value = neutron_dhcp_value['return'].rstrip()
        print ("RETVALUE neutron dhcp-agent-list-hosting-net testnet: "
               "{0}".format(neutron_dhcp_value))
        if neutron_dhcp_value == "False":
            print "DHCP is NOT WORKING PROPERLY ON THE CURRENT HOST!"
            #pass

        cmd1 = "nova delete testbuild"
        cmd2 = "neutron net-delete {0}".format(neutron_net_create_value)
        tempest.test_node.run_cmd(";".join([srcmd, cmd1, cmd2]))
        print "RETVALUE DESTROYING INSTANCE AND NETWORK"

        cmd1 = "rabbitmqctl list_queues 2>&1 >/dev/null | grep Error"
        rabbit_value = tempest.test_node.run_cmd(cmd1)['return'].rstrip()
        print "RabbitMQ should be running!"
        if rabbit_value:
            print ("RabbitMQ is not functioning properly!: "
                   "{0}".format(rabbit_value))
        else:
            print "RabbitMQ is functioning properly!"

        tempest.test_node.run_cmd("service rabbitmq-server stop")
        cmd1 = "rabbitmqctl list_queues 2>&1 >/dev/null | grep Error"
        rabbit_value = tempest.test_node.run_cmd(cmd1)['return'].rstrip()
        print "RabbitMQ should NOT be running now!"
        if rabbit_value:
            print ("RabbitMQ test is working as expected. RabbitMQ is down!: "
                   "{0}".format(rabbit_value))
        else:
            print "RabbitMQ test has failed to identify a down issue!"

        tempest.test_node.run_cmd("service rabbitmq-server start")
        cmd1 = "rabbitmqctl list_queues 2>&1 >/dev/null | grep Error"
        rabbit_value = tempest.test_node.run_cmd(cmd1)['return'].rstrip()
        print "RabbitMQ should be running!"
        if rabbit_value:
            print ("RabbitMQ is not functioning properly!: "
                   "{0}".format(rabbit_value))
        else:
            print "RabbitMQ is functioning properly!"

        #tempest.test()

        self.controller1.power_on()
        sleep(5)

    def collect_results(self):
        """
        Collect report and merge tests
        """
        xunit_merge()

    def test(self):
        self.prepare()
        self.run_tests()
        self.collect_results()
