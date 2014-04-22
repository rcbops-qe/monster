"""
Provides classes of nodes (server entities)
"""
import logging
import types

from time import sleep
from monster import util
from monster.server_helper import ssh_cmd, scp_to, scp_from

logger = logging.getLogger(__name__)


class Node(object):
    """
    A individual computation entity to deploy a part OpenStack onto
    Provides server related functions
    """
    def __init__(self, ip, user, password, product, environment,
                 deployment, provisioner, status=None):
        self.ipaddress = ip
        self.user = user
        self.password = password
        self.product = product
        self.environment = environment
        self.deployment = deployment
        self.provisioner = provisioner
        self.features = []
        self._cleanups = []
        self.status = status or "provisioning"

    def __repr__(self):
        """ Print out current instance
        :rtype: string
        """
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            # We want to not print the deployment because
            # it is a circular reference
            if attr not in ['deployment', 'password']:
                if attr == 'features':
                    features = "\tFeatures: {0}".format(
                        ", ".join(map(str, self.features)))
                elif isinstance(getattr(self, attr), types.NoneType):
                    outl += '\n\t{0} : {1}'.format(attr, 'None')
                else:
                    outl += '\n\t{0} : {1}'.format(attr, getattr(self, attr))
        return "\n".join([outl, features])

    @property
    def os_name(self):
        return self['platform']

    def get_creds(self):
        return self.ipaddress, self.user, self.password

    def run_cmd(self, remote_cmd, user='root', password=None, attempts=None):
        """
        Runs a command on the node
        :param remote_cmd: command to run on the node
        :type remote_cmd: string
        :param user: user to run the command as
        :type user: string
        :param password: password to authenticate with
        :type password:: string
        :param attempts: number of times
        :type attempts: number of times to attempt a successfully run cmd
        :rtype: dict
        """
        user = user or self.user
        password = password or self.password
        logger.info("Running: {0} on {1}".format(remote_cmd, self.name))
        count = attempts or 1
        ret = ssh_cmd(self.ipaddress, remote_cmd=remote_cmd,
                      user=user, password=password)
        while not ret['success'] and count:
            ret = ssh_cmd(self.ipaddress, remote_cmd=remote_cmd,
                          user=user, password=password)
            count -= 1
            if not ret['success']:
                # sleep for a few seconds, allows services time to do things
                sleep(5)

        if not ret['success'] and attempts:
            raise Exception("Failed to run {0} after {1} attempts".format(
                remote_cmd, attempts))

        return ret

    def scp_to(self, local_path, user=None, password=None, remote_path=""):
        """
        Sends a file to the node
        :param user: user to run the command as
        :type user: string
        :param password: password to authenticate with
        :type password:: string
        """
        user = user or self.user
        password = password or self.password
        logger.info("SCP: {0} to {1}:{2}".format(local_path, self.name,
                                                 remote_path))
        return scp_to(self.ipaddress,
                      local_path,
                      user=user,
                      password=password,
                      remote_path=remote_path)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        """
        Retreives a file from the node
        """
        user = user or self.user
        password = password or self.password
        logger.info("SCP: {0}:{1} to {2}".format(self.name, remote_path,
                                                 local_path))
        return scp_from(self.ipaddress,
                        remote_path,
                        user=user,
                        password=password,
                        local_path=local_path)

    def pre_configure(self):
        """Pre configures node for each feature"""
        self.status = "pre-configure"

        logger.info("Updating node dist / packages")
        self.update_packages(True)

        for feature in self.features:
            log = "Node feature: pre-configure: {0}".format(str(feature))
            logger.debug(log)
            feature.pre_configure()

    def apply_feature(self):
        self.status = "apply-feature"
        """Applies each feature"""
        for feature in self.features:
            log = "Node feature: apply: {0}".format(str(feature))
            logger.debug(log)
            feature.apply_feature()

    def post_configure(self):
        """Post configures node for each feature"""
        self.status = "post-configure"
        for feature in self.features:
            log = "Node feature: post-configure: {0}".format(str(feature))
            logger.debug(log)
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features"""
        self['in_use'] = ",".join(map(str, self.features))
        self.pre_configure()
        self.apply_feature()
        self.post_configure()
        self.status = "done"

    def upgrade(self):
        """Upgrades node based on features"""
        for feature in self.features:
            log = "Node feature: upgrade: {0}".format(str(feature))
            logger.info(log)
            feature.upgrade()

    def update_packages(self, dist_upgrade=False):
        """
        Updates installed packages
        """

        upgrade_cmds = []

        if 'ubuntu' in self.os_name:
            upgrade_cmds.append('apt-get update')
            if dist_upgrade:
                upgrade_cmds.append('apt-get dist-upgrade -y')
            else:
                upgrade_cmds.append('apt-get upgrade -y')
        elif self.os_name in ['centos', 'redhat']:
            upgrade_cmds.append('yum update -y')
        else:
            raise NotImplementedError(
                "{0} is a non supported platform".format(self.os_name))
        upgrade_cmd = '; '.join(upgrade_cmds)

        logger.info('Updating Distribution Packages')
        self.run_cmd(upgrade_cmd)

    def install_package(self, package):
        """
        Installs given package

        :param package: package to install
        :type package: String
        :rtype: function
        """

        # Need to make this more machine agnostic (jwagner)
        if self.os_name == "ubuntu":
            command = 'apt-get install -y {0}'.format(package)
        if self.os_name in ["centos", "rhel"]:
            command = 'yum install -y {0}'.format(package)

        return self.run_cmd(command)

    def check_package(self, package):
        """
        Checks to see if a package is installed
        """

        if self.os_name == "ubuntu":
            chk_cmd = "dpkg -l | grep {0}".format(package)
        if self.os_name in ["centos", "rhel"]:
            chk_cmd = "rpm -a | grep {0}".format(package)
        else:
            logger.info(
                "Operating system not supported at this time")

        return self.run_cmd(chk_cmd)

    def get_vmnet_iface(self):
        """
        Return the iface that our vm data network will live on
        """
        return util.config['environments']['bridge_devices']['data']

    def destroy(self):
        logger.info("Destroying node:{0}".format(self.name))
        for feature in self.features:
            log = "Node feature: destroy: {0}".format(str(feature))
            logger.debug(log)
            feature.destroy()
        self.provisioner.destroy_node(self)
        self.status = "Destroyed"

    def feature_in(self, feature):
        if feature in (feature.__class__.__name__.lower()
                       for feature in self.features):
            return True
        return False

    @property
    def feature_names(self):
        return [feature.__class__.__name__.lower() for feature in
                self.features]

    def power_off(self):
        self.provisioner.power_down(self)

    def power_on(self):

        self.provisioner.power_up(self)
