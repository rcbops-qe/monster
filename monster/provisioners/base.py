import logging
import monster.active as active

logger = logging.getLogger(__name__)


class Provisioner(object):
    """Provisioner class template.
    Enforce implementation of provision and destroy_node and naming convention.
    """

    nodes = []

    def __repr__(self):
        return self.__class__.__name__.lower()

    def provision(self, deployment, specs):
        """Provisions nodes.
        :param deployment: Deployment to provision for
        :type deployment: Deployment
        :rtype: list (chef.Node)
        """
        raise NotImplementedError

    def post_provision(self, node):
        """Tasks to be done after a node is provisioned.
        :param node: Node object to be tasked
        :type node: monster.nodes.base.Node
        """
        pass

    def destroy_node(self, node):
        """Destroys node.
        :param node: node to destroy
        :type node: monster.nodes.base.Node
        """
        raise NotImplementedError

    def power_down(self, node):
        """Turns a node off.
        :param node: node to power off
        :type node: monster.nodes.base.Node
        """
        raise NotImplementedError

    def power_up(self, node):
        """Turns a node on.
        :param node: node to power on
        :type node: monster.nodes.base.Node
        """
        raise NotImplementedError

    def build_nodes(self, deployment, specs):
        """Provisions a new set of nodes for a deployment."""

        # nodes_to_wrap =  self.provision(deployment, specs)
        self.provision(deployment, specs)
        # this now returns a single dict with a node's server, pass, and name.
        # we want to handle threading in the deployment
        # pychef in the orchestrator
        # and chefserver in the features


        #TODO: fix this before next commit!
        built_nodes = []
        for node in nodes_to_wrap:
            wrapped_node = deployment.wrap_node(node)
            self.post_provision(wrapped_node)
            built_nodes.append(wrapped_node)

        for node, features in zip(built_nodes, specs):
            node.add_features(features)
        return built_nodes
