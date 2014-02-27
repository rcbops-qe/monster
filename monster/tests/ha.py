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

        self.fail_node(self.controller1)

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
        tempest.test()

        self.controller1.power_on()
        sleep

    def collect_results(self):
        """
        Collect report and merge tests
        """
        xunit_merge()

    def test(self):
        self.prepare()
        self.run_tests()
        self.collect_results()
