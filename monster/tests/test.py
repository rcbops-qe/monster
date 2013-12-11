"""
Module to test OpenStack deployments
"""

import os
from string import Template
from itertools import ifilter, chain

from monster import util

from novaclient.v1_1.client import Client as novaclient


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


class Tempest(Test):
    def __init__(self, deployment):
        super(Tempest, self).__init__(deployment)
        self.path = "/tmp/%s.conf" % self.deployment.name
        self.test_node = next(self.deployment.search_role("controller"))
        self.tempest_config = dict(
            identity="", user1_user="", user1_password="", user1_tenant="",
            user2_user="", user2_password="", user2_tenant="", admin_user="",
            admin_password="", admin_tenant="", image_id1="", image_id2="",
            public_network_id="", public_router_id="", storage_protocol="",
            vendor_name="", glance_ip="", aws_access="", aws_secret="",
            horizon="", cinder_enabled="", neutron_enabled="",
            glance_enabled="", swift_enabled="", heat_enabled="", nova_ip=""
        )
        self.xunit_file = ""

    def prepare(self):
        """
        Sets up tempest repo, python requirements, and config
        """
        env = self.deployment.environment
        env.override_attributes['glance']['image_upload'] = True
        env.save()
        self.test_node.add_run_list_item(["recipe[tempest]"])
        self.test_node.run()

        # install python requirements for tempest
        tempest_dir = util.config['tests']['tempest']['dir']
        install_cmd = "python {0}/tools/install_venv.py".format(tempest_dir)
        self.test_node.run_cmd(install_cmd)

        # Build and send config
        self.build_config()
        tempest_dir = util.config['tests']['tempest']['dir']
        rem_config_path = "{0}/etc/tempest.conf".format(tempest_dir)
        self.test_node.run_cmd("rm {0}".format(rem_config_path))
        self.test_node.scp_to(self.path, remote_path=rem_config_path)

    def run_tests(self):
        # remove tempest cookbook. subsequent runs will fail
        self.test_node.remove_run_list_item('recipe[tempest]')
        exclude = ['volume', 'resize', 'floating']
        self.test_from(self.test_node, xunit=True, exclude=exclude)

    def collect_results(self):
        self.wait_for_results()
        self.test_node.scp_from(self.xunit_file, local_path=".")
        util.xunit_merge()

    def tempest_configure(self):
        tempest = self.tempest_config
        override = self.deployment.environment.override_attributes
        controller = next(self.deployment.search_role("controller"))

        if "highavailability" in self.deployment.feature_names():
            #use vips
            vips = override['vips']
            tempest['identity'] = vips['keystone-service-api']
            tempest['glance_ip'] = vips['glance-api']
            tempest['horizon'] = vips['horizon-dash']
            tempest['nova_ip'] = vips['nova-api']
        else:
            # use controller1
            tempest['identity'] = controller.ipaddress
            tempest['glance_ip'] = controller.ipaddress
            tempest['horizon'] = controller.ipaddress
            tempest['nova_ip'] = controller.ipaddress

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
        tempest['admin_password'] = users[admin_user][
            'password']
        tempest['admin_tenant'] = users[admin_user][
            'roles']['admin'][0]
        url = "http://{0}:5000/v2.0".format(tempest['glance_ip'])
        compute = novaclient(tempest['admin_user'],
                             tempest['admin_password'],
                             tempest['admin_tenant'],
                             url,
                             service_type="compute")
        image_ids = (i.id for i in compute.images.list())
        try:
            tempest['image_id1'] = next(image_ids)
        except StopIteration:
            util.logger.error("No glance images available")
            tempest['image_id1']
        try:
            tempest['image_id2'] = next(image_ids)
        except StopIteration:
            tempest['image_id2'] = tempest['image_id1']

        # tempest.public_network_id = None
        # tempest.public_router_id = None

        featured = lambda x: self.deployment.feature_in(x)
        tempest['cinder_enabled'] = False
        if featured('cinder'):
            tempest['cinder_enabled'] = True
            tempest['storage_protocol'] = override['cinder']['storage'][
                'provider']
            tempest['vendor_name'] = "Open Source"

        tempest['neutron_enabled'] = True if featured('neutron') else False
        tempest['glance_enabled'] = True if featured('glance') else False
        tempest['swift_enabled'] = True if featured('swift') else False
        tempest['heat_enabled'] = True if featured('orchestration') else False

    def build_networks(self):
        pass

    def build_config(self):
        self.build_networks()

        self.tempest_configure()
        template_path = os.path.join(os.path.dirname(
            os.path.abspath(__file__)), os.pardir, os.pardir,
            "files/tempest.conf")

        with open(template_path) as f:
            template = Template(f.read()).substitute(
                self.tempest_config)

        with open(self.path, 'w') as w:
            util.logger.info("Writing tempest config:{0}".
                             format(self.path))
            util.logger.debug(template)
            w.write(template)

    def test_from(self, node, xunit=False, tags=None, exclude=None,
                  paths=None, config_path=None):
        """
        Runs tests from node
        @param xunit: Produce xunit report
        @type xunit: Boolean
        @param tags: Tags to pass the nosetests
        @type tags: list
        @param exclude: Expressions to exclude
        @param exclude: list
        @param paths: Paths to load tests from (compute, compute/servers...)
        @param paths: list
        """

        tempest_dir = util.config['tests']['tempest']['dir']
        checkout = "cd {0}; git checkout stable/havana".format(tempest_dir)
        node.run_cmd(checkout)

        xunit_file = "{0}.xml".format(node.name)
        xunit_flag = ''
        if xunit:
            xunit_flag = '--with-xunit --xunit-file=%s' % xunit_file

        tag_flag = "-a " + " -a ".join(tags) if tags else ""

        exclude_flag = "-e " + " -e ".join(exclude) if exclude else ''

        test_map = util.config['tests']['tempest']['test_map']
        if not paths:
            features = self.deployment.feature_names()
            paths = ifilter(None, set(
                chain(*ifilter(None, (
                    test_map.get(feature, None) for feature in features)))))
        path_args = " ".join(paths)
        config_arg = ""
        if config_path:
            config_arg = "-c {0}".format(config_path)
        venv_bin = ".venv/bin"
        tempest_command = (
            "source {0}/{6}/activate; "
            "python -u {0}/{6}/nosetests -w "
            "{0}/tempest/api {5} "
            "{1} {2} {3} {4}".format(tempest_dir, xunit_flag,
                                     tag_flag, path_args,
                                     exclude_flag, config_arg, venv_bin)
        )
        screen = [
            "screen -d -m -S tempest -t shell -s /bin/bash",
            "screen -S tempest -X screen -t tempest",
            "export NL=`echo -ne '\015'`",
            'screen -S tempest -p tempest -X stuff "{0}$NL"'.format(
                tempest_command)
        ]
        command = "; ".join(screen)
        node.run_cmd(command)

    def wait_for_results():
        cmd = 'stat -c "%s" test-controller.xml'
        result = self.test_node.run_cmd(cmd)['return'].rstrip()
        while result == "0":
            util.logger.info("Waiting for test results")
            sleep(10)
            result = self.test_node.run_cmd(cmd)['return'].rstrip()


class CloudCafe(Test):
    def __init__(self, deployment):
        super(Tempest, self).__init__(deployment)

    def test(self):
        raise NotImplementedError
