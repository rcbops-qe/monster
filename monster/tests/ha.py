"""
Module to test HA OpenStack deployments
"""
from time import sleep

from monster.util import xunit_merge
from monster.tests.tempest import Tempest


class HA_Test(Tempest):
    """
    Parent class to test OpenStack deployments
    """

    def __init__(self, deployment):
        super(HA_Test, self).__init__(deployment)
        controllers = self.deployment.search_role("controller")
        self.controller1 = controllers[0]
        self.controller2 = controllers[1]

    def keepalived_fail(self, node):
        node.run_cmd("service keepalived stop")

    def keepalived_restore(self, node):
        node.run_cmd("service keepalived start")

    def move_vips_from(self, node):
        self.keepalived_fail(node)
        sleep(30)               # wait for vips to leave
        self.keepalived_restore(node)
        sleep(30)               # wait for node to be ready

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
        tempest = Tempest(self.deployment, unit=True, node=self.controller2)
        tempest.test()

        self.controller1.power_on()

    def collect_results(self):
        """
        Collect report and merge tests
        """
        xunit_merge()

    def test(self):
        self.prepare()
        self.run_tests()
        self.collect_results()
