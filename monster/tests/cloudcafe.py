"""
Module to test OpenStack deployments with CloudCafe
"""

from monster.tests.test import Test


class CloudCafe(Test):
    def __init__(self, deployment):
        super(CloudCafe, self).__init__(deployment)

    def test(self):
        raise NotImplementedError
