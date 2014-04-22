from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum


def get_test_suite_for(self, deployment):
    """Given rcbops branch, returns tempest branch.
    :param branch: branch of rcbops
    :type branch: string
    :rtype: string
    """
    if deployment.branch and "grizzly" in deployment.branch:
        tempest = TempestQuantum(deployment)
    else:
        tempest = TempestNeutron(deployment)
    return tempest
