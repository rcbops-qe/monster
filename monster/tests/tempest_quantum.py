"""
Module to test OpenStack deployments with Tempest in Grizzly
"""

import os
import json
import logging
import subprocess

from string import Template
from time import sleep
from itertools import ifilter, chain

import monster.active as active
from monster.tests.test import Test
from monster.tests.util import xunit_merge

logger = logging.getLogger(__name__)


class TempestQuantum(Test):
    """
    Tests a deployment with Tempest
    """

    @property
    def name(self):
        return "Tempest Quantum tests"

    def __init__(self, deployment):
        super(TempestQuantum, self).__init__(deployment)
        ###############################
        # Needs to be changed!!!!
        ###############################
        self.path = "/tmp/%s.conf" % self.deployment.name
        self.test_node = next(self.deployment.search_role("controller"))
        time_cmd = subprocess.Popen(['date', '+%F_%T'],
                                    stdout=subprocess.PIPE)
        self.time = time_cmd.stdout.read().rstrip()
        self.tempest_config = dict(
            identity="", user1_user="", user1_password="", user1_tenant="",
            user2_user="", user2_password="", user2_tenant="", admin_user="",
            admin_password="", admin_tenant="", image_id1="", image_id2="",
            public_network_id="", public_router_id="", storage_protocol="",
            vendor_name="", glance_ip="", aws_access="", aws_secret="",
            horizon="", cinder_enabled="", quantum_enabled="",
            glance_enabled="", swift_enabled="", heat_enabled="", nova_ip=""
        )
        self.xunit_file = ""

    def tempest_configure(self):
        """
        Gather all the values for tempest config file
        """
        tempest = self.tempest_config
        override = self.deployment.override_attrs
        controller = next(self.deployment.search_role("controller"))
        ip = controller['rabbitmq']['address']

        if "highavailability" in self.deployment.feature_names():
            #use vips
            vips = override['vips']
            tempest['identity'] = vips['keystone-service-api']
            tempest['glance_ip'] = vips['glance-api']
            tempest['horizon'] = vips['horizon-dash']
            tempest['nova_ip'] = vips['nova-api']
        else:
            # use controller1
            tempest['identity'] = ip
            tempest['glance_ip'] = ip
            tempest['horizon'] = ip
            tempest['nova_ip'] = ip

        ec2_creds = controller['credentials']['EC2']['admin']
        tempest['aws_access'] = ec2_creds['access']
        tempest['aws_secret'] = ec2_creds['secret']

        keystone = override['keystone']
        users = keystone['users']
        non_admin_users = (user for user in users.keys()
                           if "admin" not in users[user]['roles'].keys())
        user1 = next(non_admin_users)
        tempest['user1_user'] = user1
        tempest['user1_password'] = users[user1]['password']
        tempest['user1_tenant'] = users[user1]['roles']['Member'][0]
        user2 = next(non_admin_users, None)
        if user2:
            tempest['user2_user'] = user2
            tempest['user2_password'] = users[user2]['password']
            tempest['user2_tenant'] = users[user2]['roles']['Member'][0]
        admin_user = keystone['admin_user']
        tempest['admin_user'] = admin_user
        admin_password = users[admin_user]['password']
        tempest['admin_password'] = admin_password
        tempest['admin_tenant'] = users[admin_user][
            'roles']['admin'][0]

        # create network, router, and get image ids
        url = controller['keystone']['adminURL']
        ids = self.tempest_ids(url, admin_user, admin_password)
        tempest['image_id1'] = ids['image_id1']
        tempest['image_id2'] = ids['image_id2']
        tempest['public_network_id'] = ids.get('network_id')
        tempest['public_router_id'] = ids.get('router_id')

        # discover enabled features
        featured = lambda x: self.deployment.has_feature(x)
        tempest['cinder_enabled'] = False
        if featured('cinder'):
            tempest['cinder_enabled'] = True
            tempest['storage_protocol'] = override['cinder']['storage'][
                'provider']
            tempest['vendor_name'] = "Open Source"
        tempest['quantum_enabled'] = True if featured('neutron') else False
        tempest['glance_enabled'] = True if featured('glance') else False
        tempest['swift_enabled'] = True if featured('swift') else False
        tempest['heat_enabled'] = True if featured('orchestration') else False

    def tempest_ids(self, url, user, password):
        """
        Creates a router, network, and gets image, returns their ids
        :param url: authentication url
        :type url: str
        :param user: user authenticate with
        :type user: str
        :param password: password to authenticate user
        :type password: str
        :rtype: dict
        """

        # template values
        is_quantum = self.deployment.has_feature("neutron")
        creds = {
            "USER": user,
            "PASSWORD": password,
            "URL": url,
            "IS_QUANTUM": is_quantum}
        template_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), os.pardir, os.pardir,
            "files/testing_setup_quantum.py.template")

        # apply values
        with open(template_path) as f:
            template = Template(f.read()).substitute(creds)

        # save script
        name = "{0}-testing_setup_quantum.py".format(self.deployment.name)
        path = "/tmp/{0}".format(name)
        with open(path, 'w') as w:
            logger.info("Writing test setup:{0}". format(self.path))
            logger.debug(template)
            w.write(template)

        # send script to node
        node = self.test_node
        node.scp_to(path, remote_path=name)

        # run script
        ret = node.run_cmd("python {0}".format(name))
        raw = ret['return']

        return json.loads(raw)

    def feature_test_paths(self, paths=None):
        test_map = active.config['tests']['tempest']['test_map']
        if not paths:
            features = self.deployment.feature_names()
            paths = ifilter(None, set(
                chain(*ifilter(None, (
                    test_map.get(feature, None) for feature in features)))))
        return paths

    def test_from(self, node, xunit=False, tags=None, exclude=None,
                  paths=None, config_path=None):
        """
        Runs tests from node
        @param xunit: Produce xunit report
        @type xunit: bool
        @param tags: Tags to pass the nosetests
        @type tags: list
        @param exclude: Expressions to exclude
        @param exclude: list
        @param paths: Paths to load tests from (compute, compute/servers...)
        @param paths: list
        """

        # clone Tempest
        tempest_dir = active.config['tests']['tempest']['dir']
        checkout = "cd {0}; git checkout stable/grizzly".format(tempest_dir)
        node.run_cmd(checkout)

        # format flags
        xunit_file = "{0}.xml".format(node.name)
        xunit_flag = ''
        if xunit:
            xunit_flag = '--with-xunit --xunit-file=%s' % xunit_file

        tag_flag = "-a " + " -a ".join(tags) if tags else ""

        exclude_flag = "-e " + " -e ".join(exclude) if exclude else ''

        path_args = " ".join(self.feature_test_paths())

        config_arg = ""
        if config_path:
            config_arg = "-c {0}".format(config_path)

        # build commands
        tempest_command = (
            "python -u `which nosetests` -w "
            "{0}/tempest/tests {5} "
            "{1} {2} {3} {4}".format(tempest_dir, xunit_flag,
                                     tag_flag, path_args,
                                     exclude_flag, config_arg))
        screen = [
            "screen -d -m -S tempest -t shell -s /bin/bash",
            "screen -S tempest -X screen -t tempest",
            "export NL=`echo -ne '\015'`",
            'screen -S tempest -p tempest -X stuff "{0}$NL"'.format(
                tempest_command)
        ]
        command = "; ".join(screen)

        node.run_cmd(command)

    def wait_for_results(self):
        """
        Wait for Tempest results to come be reported
        """
        cmd = 'stat -c "%s" {0}.xml'.format(self.test_node.name)
        result = self.test_node.run_cmd(cmd)['return'].rstrip()
        while result == "0":
            logger.info("Waiting for test results")
            sleep(30)
            result = self.test_node.run_cmd(cmd)['return'].rstrip()

    def clone_repo(self, branch):
        """
        Clones repo onto node
        :param branch: branch to clone
        :type branch: string
        """
        repo = active.config['tests']['tempest']['repo']
        tempest_dir = active.config['tests']['tempest']['dir']
        clone = "git clone {0} -b {1} {2}".format(repo, branch, tempest_dir)
        self.test_node.run_cmd(clone)

    @classmethod
    def tempest_branch(cls, branch):
        """
        Given rcbops branch, returns Tempest branch
        :param branch: branch of rcbops
        :type branch: string
        :rtype: string
        """
        branches = active.config['rcbops']['compute']['git']['branches']
        branch_format = "stable/{0}"
        tag_branch = ""
        if branch in branches.keys():
            tag_branch = branch_format.format(branch)
        else:
            for branch_name, tags in branches.items():
                if branch in tags:
                    tag_branch = branch_name
                else:
                    tag_branch = "master"
        return branch_format.format(tag_branch)

    def install_package_requirements(self):
        """
        Installs requirements of Tempest
        """
        if self.deployment.os_name == "centos":
            self.test_node.run_cmd("yum install -y screen libxslt-devel "
                                   "postgresql-devel python-pip python-devel")
        if self.deployment.os_name == "ubuntu":
            self.test_node.run_cmd("apt-get install -y screen python-dev "
                                   "libxml2 libxslt1-dev libpq-dev python-pip")

        # install Python requirements for Tempest
        tempest_dir = active.config['tests']['tempest']['dir']
        install_cmd = ("pip install -r "
                       "{0}/tools/pip-requires").format(tempest_dir)
        self.test_node.run_cmd(install_cmd)

    def build_config(self):
        """
        Builds Tempest config files
        """
        self.tempest_configure()
        # find template
        template_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), os.pardir, os.pardir,
            "files/tempest_quantum.conf")

        # open template and add values
        with open(template_path) as f:
            template = Template(f.read()).substitute(
                self.tempest_config)

        # save config
        with open(self.path, 'w') as w:
            logger.info("Writing tempest config: {0}".format(self.path))
            logger.debug(template)
            w.write(template)

    def send_config(self):
        """
        Sends Tempest config file to node
        """
        tempest_dir = active.config['tests']['tempest']['dir']
        rem_config_path = "{0}/etc/tempest.conf".format(tempest_dir)
        self.test_node.run_cmd("rm {0}".format(rem_config_path))
        self.test_node.scp_to(self.path, remote_path=rem_config_path)

    def prepare(self):
        """
        Sets up Tempest repo, python requirements, and config
        """
        branch = self.tempest_branch(self.deployment.branch)
        self.clone_repo(branch)
        self.install_package_requirements()
        self.build_config()
        self.send_config()

    def run_tests(self):
        """
        Runs Tempest
        """
        exclude = None
        self.test_from(self.test_node, xunit=True, exclude=exclude)

    def collect_results(self):
        """
        Collects tempest report as xunit report
        """
        self.wait_for_results()  # tests are run in screen
        self.xunit_file = self.test_node.name + "-" + self.time + ".xml"
        self.test_node.run_cmd("mv {0} {1}".format(self.test_node.name +
                                                   ".xml",
                                                   self.xunit_file))
        self.test_node.scp_from(self.xunit_file, local_path=self.xunit_file)
        self.test_node.run_cmd("killall screen")
        xunit_merge()
