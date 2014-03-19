import subprocess

from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum
from monster.tests.ha import HATest
from monster import util


class TestUtil:
    def __init__(self, deployment, args):
        self.deployment = deployment
        self.args = args

    def runHA(self):
        if not self.deployment.feature_in("highavailability"):
            util.logger.warning('High Availability was not detected as a '
                                'feature; HA tests will not be run!')
            return
        ha = HATest(self.deployment)
        self.__prepare_xml_directory()
        util.logger.info('Running High Availability test!')
        for i in range(self.args.iterations):
            util.logger.debug('Running iteration %s!' % (i + 1))
            ha.test(self.args.iterations, self.args.provider_net)

    def runTempest(self):
        branch = TempestQuantum.tempest_branch(self.deployment.branch)
        if "grizzly" in branch:
            tempest = TempestQuantum(self.deployment)
        else:
            tempest = TempestNeutron(self.deployment)
        self.__prepare_xml_directory()
        util.logger.info('Running Tempest test!')
        for i in range(self.args.iterations):
            util.logger.debug('Running iteration %s!' % (i + 1))
            tempest.test()

    def report(self):
        util.logger.info('Tests have been completed with {0} iterations!'
                         .format(self.args.iterations))

    def __get_file(ip, user, password, remote, local, remote_delete=False):
        cmd1 = 'sshpass -p {0} scp -q {1} {2}'.format(password, remote, local)
        subprocess.call(cmd1, shell=True)
        if remote_delete:
            cmd2 = ("sshpass -p {0} ssh -o UserKnownHostsFile=/dev/null "
                    "-o StrictHostKeyChecking=no -o LogLevel=quiet -l {1} {2}"
                    " 'rm *.xml;exit'".format(password, user, ip))
            subprocess.call(cmd2, shell=True)

    def __prepare_xml_directory(self):
        env = self.deployment.environment.name
        local = "./results/{0}/".format(env)
        controllers = self.deployment.search_role('controller')
        for controller in controllers:
            ip, user, password = controller.get_creds()
            remote = "{0}@{1}:~/*.xml".format(user, ip)
            self.__get_file(ip, user, password, remote, local)

            #Prepares directory for xml files to be SCPed over
            self.subprocess.call(['mkdir', '-p', '{0}'.format(local)])
