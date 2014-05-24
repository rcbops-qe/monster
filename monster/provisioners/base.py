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

    def provision(self, deployment):
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

    def build_nodes(self, deployment):
        """Provisions a new set of nodes for a deployment."""
        assert deployment.nodes == []
        nodes_to_wrap = self.provision(deployment)

        built_nodes = []
        for node in nodes_to_wrap:
            wrapped_node = deployment.wrap_node(node)
            self.post_provision(wrapped_node)
            built_nodes.append(wrapped_node)

        for node, features in zip(built_nodes, active.template['nodes']):
            node.add_features(features)
        deployment.nodes = built_nodes
