from weakref import proxy

import monster.active as active
import monster.features.base as base


class Feature(base.Feature):
    """Represents a feature on a node."""

    def __init__(self, node):
        """Initialize Node object.
        :type node: monster.nodes.base.Node
        """
        self.node = proxy(node)

    def __repr__(self):
        return self.__class__.__name__.lower()

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass

    def artifact(self):
        pass

    def upgrade(self):
        pass

    def set_run_list(self):
        """Sets the nodes run list based on the feature."""

        # have to add logic for controllers
        if hasattr(self, "number"):
            # Set the role based on the feature name and number of the node
            role = "{0}{1}".format(self.__class__.__name__.lower(),
                                   self.number)
        else:
            role = self.__class__.__name__.lower()

        # Set the run list based on the deployment config for the role
        run_list = active.config['rcbops'][self.node.product][role]['run_list']

        # Add the run list to the node
        self.node.add_run_list_item(run_list)

    def build_archive(self):
        """Builds an archive to save node information."""
        self.log_path = '/tmp/archive/var/log'
        self.etc_path = '/tmp/archive/etc'
        self.misc_path = '/tmp/archive/misc'

        build_archive_cmd = "; ".join("mkdir -p {0}".format(path)
                                      for path in (self.log_path,
                                                   self.etc_path,
                                                   self.misc_path))

        self.node.run_cmd(build_archive_cmd)

    def save_node_running_services(self):
        store_running_services = "{0} > {1}/running-services.out".format(
            self.node.deployment.list_packages_cmd, self.misc_path)
        self.node.run_cmd(store_running_services)
