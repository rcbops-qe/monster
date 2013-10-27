"""
OpenStack deployments
"""

import types
from monster import util


class Deployment(object):
    """Base for OpenStack deployments
    """

    def __init__(self, name, os_name, branch, config, status="provisioning"):
        self.name = name
        self.os_name = os_name
        self.branch = branch
        self.config = config
        self.features = []
        self.nodes = []
        self.status = status

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            if attr == 'features':
                features = "\tFeatures: {0}".format(
                    ", ".join((str(f) for f in self.features)))
            elif attr == 'nodes':
                nodes = "\tNodes: {0}".format(
                    "".join((str(n) for n in self.nodes)))
            elif isinstance(getattr(self, attr), types.NoneType):
                outl += '\n\t{0} : {1}'.format(attr, 'None')
            else:
                outl += '\n\t{0} : {1}'.format(attr, getattr(self, attr))

        return "\n".join([outl, features, nodes])

    def destroy(self):
        """ Destroys an OpenStack deployment """
        self.status = "destroying"
        util.logger.info("Destroying deployment:{0}".format(self.name))
        for node in self.nodes:
            node.destroy()
        self.status = "destroyed"

    def update_environment(self):
        """Pre configures node for each feature"""
        self.status = "loading environment"
        for feature in self.features:
            log = "Deployment feature: update environment: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.update_environment()
        util.logger.debug(self.environment)
        self.status = "environment ready"

    def pre_configure(self):
        """Pre configures node for each feature"""
        self.status = "pre-configure"
        for feature in self.features:
            log = "Deployment feature: pre-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.pre_configure()

    def build_nodes(self):
        self.status = "building nodes"
        """Builds each node"""
        for node in self.nodes:
            node.build()
        self.status = "nodes built"

    def post_configure(self):
        """Post configures node for each feature"""
        self.status = "post-configure"
        for feature in self.features:
            log = "Deployment feature: post-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features"""
        util.logger.debug("Deployment step: update environment")
        self.update_environment()
        util.logger.debug("Deployment step: pre-configure")
        self.pre_configure()
        util.logger.debug("Deployment step: build nodes")
        self.build_nodes()
        util.logger.debug("Deployment step: post-configure")
        self.post_configure()
        self.status = "done"

    def search_role(self, feature):
        """
        Returns nodes the have the desired role
        """
        return (node for node in
                self.nodes if feature in
                (str(f).lower() for f in node.features))

    def test(self):
        """
        Run tests on deployment
        """
        pass
