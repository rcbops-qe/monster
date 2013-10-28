"""
Provides classes of nodes (server entities)
"""

import types
from monster import util
from monster.server_helper import ssh_cmd, scp_to, scp_from


class Node(object):
    """
    A individual computation entity to deploy a part OpenStack onto
    Provides server related functions
    """
    def __init__(self, ip, user, password, os, product, environment,
                 deployment, provisioner, status=None):
        self.ipaddress = ip
        self.user = user
        self.password = password
        self.os_name = os
        self.product = product
        self.environment = environment
        self.deployment = deployment
        self.provisioner = provisioner
        self.features = []
        self._cleanups = []
        self.status = status or "provisioning"

    def __repr__(self):
        """ Print out current instance
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

    def run_cmd(self, remote_cmd, user=None, password=None):
        """
        Runs a command on the node
        """
        user = user or self.user
        password = password or self.password
        util.logger.info("Running: {0} on {1}".format(remote_cmd, self.name))
        return ssh_cmd(self.ipaddress, remote_cmd=remote_cmd, user=user,
                       password=password)

    def scp_to(self, local_path, user=None, password=None, remote_path=""):
        """
        Sends a file to the node
        """
        user = user or self.user
        password = password or self.password
        return scp_to(self.ipaddress, local_path, user=user, password=password,
                      remote_path=remote_path)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        """
        Retreives a file from the node
        """
        user = user or self.user
        password = password or self.password
        return scp_from(self.ipaddress, remote_path, user=user,
                        password=password, local_path=local_path)

    def pre_configure(self):
        """Pre configures node for each feature"""
        self.status = "pre-configure"
        for feature in self.features:
            log = "Node feature: pre-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.pre_configure()

    def apply_feature(self):
        self.status = "apply-feature"
        """Applies each feature"""
        for feature in self.features:
            log = "Node feature: update environment: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.apply_feature()

    def post_configure(self):
        """Post configures node for each feature"""
        self.status = "post-configure"
        for feature in self.features:
            log = "Node feature: post-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features"""
        self['in_use'] = ",".join(map(str, self.features))
        self.pre_configure()
        self.apply_feature()
        self.post_configure()
        self.status = "done"

    def destroy(self):
        self.status = "Destroying"
        self.provisioner.destroy_node(self)
        util.logger.info("Destroying node:{0}".format(self.name))
        self.status = "Destroyed"
