from monster import util
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum

class TempestHelper:

    @classmethod
    def get_test_suite_for(self, branch):
        """
        Given rcbops branch, returns tempest branch
        :param branch: branch of rcbops
        :type branch: string
        :rtype: string
        """
        if "grizzly" in branch:
            tempest = TempestQuantum(self.deployment)
        else:
            tempest = TempestNeutron(self.deployment)
        return tempest
