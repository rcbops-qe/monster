import logging

logger = logging.getLogger(__name__)


class Provisioner(object):
    """Provisioner class template.
    Enforce implementation of provision and destroy_node and naming convention.
    """

    def build_node(self, deployment, specs):
        node = self.provision_node(deployment, specs)
        self.post_provision(node)
        return node

    def __repr__(self):
        return self.__class__.__name__.lower()

    def provision_node(self, deployment, specs):
        """Provisions a node.
        :param deployment: Deployment to provision for
        :type deployment: Deployment
        :rtype: monster.nodes.base.Node
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
