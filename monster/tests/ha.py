"""
Module to test HA OpenStack deployments
"""
from monster.util import xunit_merge
from monster.tests.tempest import Tempest


class HA_Test(Tempest):
    """
    Parent class to test OpenStack deployments
    """

    def __init__(self, deployment):
        super(HA_Test, self).__init__(deployment)

    def prepare(self):
        pass

    def run_tests(self):
        pass

    def collect_results(self):
        xunit_merge()

    def test(self):
        self.prepare()
        self.run_tests()
        self.collect_results()
