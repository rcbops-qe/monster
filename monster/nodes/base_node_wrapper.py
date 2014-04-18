"""
Provides classes of nodes (server entities)
"""

import types
from lazy import lazy
from time import sleep
from monster import util
from monster.nodes.os_node_strategy import OS
from monster.server_helper import ssh_cmd, scp_to, scp_from
from monster.features import node_feature


class BaseNodeWrapper(object):
    """
    A individual computation entity to deploy a part OpenStack onto
    Provides server related functions
    """
    def __init__(self, name, ip, user, password, product,
                 deployment, provisioner):
        self.ipaddress = ip
        self.user = user
        self.name = name
        self.password = password
        self.product = product
        self.deployment = deployment
        self.provisioner = provisioner
        self.features = []
        self._cleanups = []
        self.status = "Unknown"

    def __repr__(self):
        """
        Print out current instance
        :rtype: string
        """
        features = []
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

    def __getitem__(self, item):
        raise NotImplementedError()

    def __setitem__(self, item, value):
        raise NotImplementedError()

    def run_cmd(self, remote_cmd, user='root', password=None, attempts=None):
        """
        Runs a command on the node
        :param remote_cmd: command to run on the node
        :type remote_cmd: str
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
        util.logger.info("Running: {0} on {1}".format(remote_cmd, self.name))
        count = attempts or 1
        ret = ssh_cmd(self.ipaddress, remote_cmd=remote_cmd,
                      user=user, password=password)
        while not ret['success'] and count:
            ret = ssh_cmd(self.ipaddress, remote_cmd=remote_cmd,
                          user=user, password=password)
            count -= 1
            if not ret['success']:
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
        util.logger.info("SCP: {0} to {1}:{2}".format(local_path, self.name,
                                                      remote_path))
        return scp_to(self.ipaddress,
                      local_path,
                      user=user,
                      password=password,
                      remote_path=remote_path)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        """
        Retrieves a file from the node
        """
        user = user or self.user
        password = password or self.password
        util.logger.info("SCP: {0}:{1} to {2}".format(self.name, remote_path,
                                                      local_path))
        return scp_from(self.ipaddress,
                        remote_path,
                        user=user,
                        password=password,
                        local_path=local_path)

    def pre_configure(self):
        """
        Pre configures node for each feature
        """
        self.status = "pre-configure"

        util.logger.info("Updating node dist / packages")
        self.update_packages(True)

        for feature in self.features:
            log = "Node feature: pre-configure: {0}".format(str(feature))
            util.logger.debug(log)
            feature.pre_configure()

    def save_to_node(self):
        """
        Save deployment restore attributes to chef environment
        """
        features = [str(f).lower() for f in self.features]
        node = {'features': features,
                'status': self.status,
                'provisioner': str(self.provisioner)}
        self['archive'] = node

    def add_features(self, features):
        """
        Adds a list of feature classes
        """
        util.logger.debug("node:{0} feature add:{1}".format(self.name,
                                                            features))
        classes = util.module_classes(node_feature)
        for feature in features:
            feature_class = classes[feature](self)
            self.features.append(feature_class)

        # save features for restore
        self.save_to_node()

    def apply_feature(self):
        """
        Applies each feature
        """
        self.status = "apply-feature"
        for feature in self.features:
            log = "Node feature: apply: {0}".format(str(feature))
            util.logger.debug(log)
            feature.apply_feature()

    def post_configure(self):
        """
        Post configures node for each feature
        """
        self.status = "post-configure"
        for feature in self.features:
            log = "Node feature: post-configure: {0}".format(str(feature))
            util.logger.debug(log)
            feature.post_configure()

    def build(self):
        """
        Runs build steps for node's features
        """
        self['in_use'] = ", ".join(map(str, self.features))
        self.pre_configure()
        self.apply_feature()
        self.post_configure()
        self.status = "done"

    def upgrade(self):
        """
        Upgrades node based on features
        """
        for feature in self.features:
            log = "Node feature: upgrade: {0}".format(str(feature))
            util.logger.info(log)
            feature.upgrade()

    def update_packages(self, dist_upgrade=False):
        """
        Updates installed packages
        """
        util.logger.info('Updating Distribution Packages')
        upgrade_command = self.os.update_dist(dist_upgrade)
        self.run_cmd(upgrade_command)

    def install_package(self, package):
        """
        :param package: package to install
        :type package: str
        :rtype: function
        """
        install_command = self.os.install_package(package)
        return self.run_cmd(install_command)

    def check_package(self, package):
        """
        Checks to see if a package is installed
        """
        check_package_command = self.os.check_package(package)
        return self.run_cmd(check_package_command)

    def destroy(self):
        util.logger.info("Destroying node:{0}".format(self.name))
        for feature in self.features:
            log = "Node feature: destroy: {0}".format(str(feature))
            util.logger.debug(log)
            feature.destroy()
        self.provisioner.destroy_node(self)
        self.status = "Destroyed"

    def power_off(self):
        self.provisioner.power_down(self)

    def power_on(self):
        self.provisioner.power_up(self)

    def has_feature(self, feature_name):
        return feature_name in self.feature_names

    @property
    def feature_names(self):
        return [str(feature) for feature in self.features]

    @property
    def creds(self):
        return self.ipaddress, self.user, self.password

    @property
    def os_name(self):
        return self['platform']

    @property
    def vmnet_iface(self):
        """
        Return the iface that our vm data network will live on
        """
        return util.config['environments']['bridge_devices']['data']

    @lazy
    def os(self):
        return OS(self.os_name)
