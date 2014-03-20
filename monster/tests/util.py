import logging
import subprocess

from monster.tests.tempest_helper import get_test_suite_for
from monster.tests.ha import HATest
from monster import util


logger = logging.getLogger("{0}.log".format(__name__))


class TestUtil:
    def __init__(self, deployment, iterations):
        self.deployment = deployment
        self.iterations = iterations

    def run_ha(self):
        if not self.deployment.feature_in("highavailability"):
            logger.warning('High Availability was not detected as a '
                           'feature; HA tests will not be run!')
            return
        ha = HATest(self.deployment)
        self.__run(ha)

    def run_tempest(self):
        test_suite = get_test_suite_for(self.deployment)
        self.__run(test_suite)

    def run_cloudcafe(self):
        pass

    def get_tests(self, tests):
        tests_methods = []
        if 'ha' or 'all' in tests:
            tests_methods.append(self.run_ha)
        if 'tempest' or 'all' in tests:
            tests_methods.append(self.run_tempest)
        return tests_methods

    def __run(self, test_suite):
        self.__prepare_xml_directory()
        util.logger.info('Running {0}!'.format(test_suite.name))
        for i in range(self.iterations):
            util.logger.debug('Running iteration %s!' % (i + 1))
            test_suite.test()
        util.logger.info('{0} have been completed with {1} iterations!'
                         .format(test_suite.name, self.iterations))

    def __prepare_xml_directory(self):
        env = self.deployment.environment.name
        local = "./results/{0}/".format(env)
        controllers = self.deployment.search_role('controller')
        for controller in controllers:
            ip, user, password = controller.get_creds()
            remote = "{0}@{1}:~/*.xml".format(user, ip)
            self.__get_file(ip, user, password, remote, local)

            #Prepares directory for xml files to be SCPed over
            subprocess.call(['mkdir', '-p', '{0}'.format(local)])

    def __get_file(ip, user, password, remote, local, remote_delete=False):
        cmd1 = 'sshpass -p {0} scp -q {1} {2}'.format(password, remote, local)
        subprocess.call(cmd1, shell=True)
        if remote_delete:
            cmd2 = ("sshpass -p {0} ssh -o UserKnownHostsFile=/dev/null "
                    "-o StrictHostKeyChecking=no -o LogLevel=quiet -l {1} {2}"
                    " 'rm *.xml;exit'".format(password, user, ip))
            subprocess.call(cmd2, shell=True)
