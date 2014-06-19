"""Provides classes of nodes (server entities)"""
import logging
import time

from weakref import proxy
from lazy import lazy

import monster.features.node.features as node_features
import monster.nodes.util as node_util
import monster.active as active

from monster.utils.access import scp_from, scp_to, ssh_cmd
from monster.utils.introspection import module_classes


logger = logging.getLogger(__name__)


class Node(object):
    """An individual computation entity to deploy a part OpenStack onto.
    Provides server-related functions.
    """
    def __init__(self, name, ip, user, password, deployment, uuid=None):
        self.ipaddress = ip
        self.uuid = uuid
        self.user = user
        self.name = name
        self.password = password
        self.product = deployment.product
        self.deployment = proxy(deployment)
        self.provisioner_name = deployment.provisioner_name
        self.features = []
        self.status = "unknown"

    def __repr__(self):
        return ('\nclass: Node \n\tname: {}\n\t'.format(self.name) +
                '\n\t'.join(sorted('{}: {}'.format(attr, getattr(self, attr))
                            for attr in self.__dict__
                            if attr not in ['name', 'deployment', 'run_list',
                                            'feature_names', 'environment'])))

    def __getitem__(self, item):
        raise NotImplementedError()

    def __setitem__(self, item, value):
        raise NotImplementedError()

    def run_cmd(self, cmd, user=None, password=None, attempts=3):
        """Runs a command on the node.
        :param cmd: command to run on the node
        :type cmd: str
        :param user: user to run the command as
        :type user: str
        :param password: password to authenticate with
        :type password:: str
        :param attempts: number of times
        :type attempts: int
        :rtype: dict
        """
        user = user or self.user
        password = password or self.password

        for attempt in range(attempts):
            result = ssh_cmd(self.ipaddress, cmd, user, password,
                             hostname=self.name)
            if result['success']:
                break
            else:
                time.sleep(0.5)
        else:
            raise Exception("Failed to run '{command}' after {n} attempts"
                            .format(command=cmd, n=attempts))
        return result

    def scp_to(self, local_path, user=None, password=None, remote_path=""):
        """Sends a file to the node.
        :param user: user to run the command as
        :type user: str
        :param password: password to authenticate with
        :type password:: string
        """
        user = user or self.user
        password = password or self.password
        return scp_to(self.ipaddress, local_path, remote_path,
                      user=user, password=password)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        """Retrieves a file from the node."""
        user = user or self.user
        password = password or self.password
        return scp_from(self.ipaddress, remote_path, local_path,
                        user=user, password=password)

    def pre_configure(self):
        """Preconfigures node for each feature."""
        self.status = "pre-configure"

        logger.info("Updating node dist / packages")
        if 'rackspace' in str(self.provisioner):
            dist_upgrade = False
        else:
            dist_upgrade = True

        self.update_packages(dist_upgrade)

        for feature in self.features:
            log = "Node feature: pre-configure: {}".format(feature)
            logger.debug(log)
            feature.pre_configure()

    def add_features(self, features):
        """Adds a list of feature classes."""
        logger.debug("node: {} add features: {}".format(self.name, features))
        classes = module_classes(node_features)
        for feature in features:
            feature_class = classes[feature](self)
            self.features.append(feature_class)

    def apply_feature(self):
        """Applies each feature."""
        self.status = "apply-feature"
        for feature in self.features:
            log = "Node feature: apply: {}".format(feature)
            logger.debug(log)
            feature.apply_feature()

    def feature(self, feature_name):
        """Returns feature of a given name, if the node has it."""
        try:
            return next(feature for feature in self.features
                        if str(feature) == feature_name)
        except StopIteration:
            logger.warning("{} does not have the feature {}"
                           .format(self.name, feature_name))

    def post_configure(self):
        """Post-configures node for each feature."""
        self.status = "post-configure"
        for feature in self.features:
            log = "Node feature: post-configure: {}".format(feature)
            logger.debug(log)
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features."""
        self['in_use'] = self.feature_names
        self.pre_configure()
        self.apply_feature()
        self.post_configure()
        self.status = "done"

    def upgrade(self):
        """Upgrades node based on features."""
        for feature in self.features:
            logger.info("Node feature: upgrade: {}".format(feature))
            feature.upgrade()

    def initial_update(self):
        for command in self.os.initial_update_cmds:
            self.run_cmd(command)

    def update_packages(self, dist_upgrade=False):
        """Updates installed packages."""
        logger.info('Updating Distribution Packages')
        self.run_cmd(self.os.update_dist_cmd(dist_upgrade))

    def install_package(self, package):
        """Installs a package on an Ubuntu, CentOS, or RHEL node."""
        return self.run_cmd(self.os.install_package_cmd(package))

    def install_packages(self, packages):
        """Installs multiple packages."""
        return self.install_package(" ".join(packages))

    def check_package(self, package):
        """Checks to see if a package is installed."""
        return self.run_cmd(self.os.check_package_cmd(package))

    def install_ruby_gem(self, gem):
        self.run_cmd('source /usr/local/rvm/scripts/rvm; '
                     'gem install --no-rdoc --no-ri {gem}'.format(gem=gem))

    def install_ruby_gems(self, gems):
        self.install_ruby_gem(" ".join(gems))

    def remove_chef(self):
        self.run_cmd(self.os.remove_chef_cmd)

    def mkswap(self, size=2):
        for command in self.os.mkswap_cmds(size):
            self.run_cmd(command)

    def destroy(self):
        logger.info("Destroying node: {node}".format(node=self.name))
        for feature in self.features:
            logger.debug("Destroying feature: {}".format(feature))
            feature.destroy()
        self.provisioner.destroy_node(self)
        self.status = "Destroyed"

    def power_off(self):
        self.provisioner.power_down(self)

    def power_on(self):
        self.provisioner.power_up(self)

    def has_feature(self, feature_name):
        return feature_name in (str(feature) for feature in self.features)

    @property
    def creds(self):
        return self.ipaddress, self.user, self.password

    @property
    def os_name(self):
        return self.deployment.os_name

    @property
    def vmnet_iface(self):
        """Return the iface that our VM data network will live on."""
        return active.config['environments']['bridge_devices']['data']

    @property
    def provisioner(self):
        return self.deployment.provisioner

    @lazy
    def feature_names(self):
        return [str(feature) for feature in self.features]

    @lazy
    def os(self):
        return node_util.get_os(self.os_name)
