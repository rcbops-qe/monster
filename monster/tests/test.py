"""
Module to test OpenStack deployments
"""


class Test(object):
    """
    Parent class to test OpenStack deployments
    """

    def __init__(self, deployment):
        self.deployment = deployment

    def prepare(self):
        pass

    def run_tests(self):
        pass

    def collect_results(self):
        pass

    def test(self):
        self.prepare()
        self.run_tests()
        self.collect_results()
