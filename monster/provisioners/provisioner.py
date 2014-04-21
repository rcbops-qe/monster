import logging
import sys
import traceback
from monster.util import module_classes
from monster.provisioners import *


logger = logging.getLogger(__name__)


class Provisioner(object):
    """
    Provisioner class template

    Enforce implementation of provision and destroy_node and naming convention
    """

    nodes = []

    def __repr__(self):
        return self.__class__.__name__.lower()

    def provision(self, template, deployment):
        """
        Provisions nodes
        :param template: template for cluster
        :type template: dict
        :param deployment: Deployment to provision for
        :type deployment: Deployment
        :rtype: list (chef.Node)
        """
        raise NotImplementedError

    def post_provision(self, node):
        """
        Tasks to be done after a node is provisioned
        :param node: Node object to be tasked
        :type node: nodes.BaseNodeWrapper
        """
        pass

    def destroy_node(self, node):
        """
        Destroys node
        :param node: node to destroy
        :type node: nodes.BaseNodeWrapper
        """
        raise NotImplementedError

    def destroy_all_nodes(self):
        """
        Destroys all Chef nodes from an OpenStack deployment
        """
        [self.destroy_node(node) for node in self.nodes]

    def power_down(self, node):
        """
        Turns a node off
        :param node: node to power off
        :type node: nodes.BaseNodeWrapper
        """
        raise NotImplementedError

    def power_up(self, node):
        """
        Turns a node on
        :param node: node to power on
        :type node: nodes.BaseNodeWrapper
        """
        raise NotImplementedError

    def reload_node_list(self, node_list, api):
        raise NotImplementedError

    def build_nodes(self, template, deployment, node_wrapper_factory):
        product = template['product']
        nodes_to_wrap = self.provision(template, deployment)
        built_nodes = []
        for node in nodes_to_wrap:
            wrapped_node = node_wrapper_factory.wrap_node(
                node, product, deployment.environment, deployment,
                provisioner=self, branch=deployment.branch)
            self.post_provision(wrapped_node)
            built_nodes.append(wrapped_node)

        for node, features in zip(built_nodes, template['nodes']):
            node.add_features(features)

        return built_nodes

    def load_nodes(self, env, deployment, node_wrapper_factory):
        loaded_nodes = []
        nodes_to_load = self.reload_node_list(env.nodes, env.local_api)
        for node in nodes_to_load:
            if not node.exists:
                logger.error("Non-existent chef node: {0}".format(node.name))
                continue
            wrapped_node = node_wrapper_factory.wrap_node(
                node, env.product, env, deployment, self,
                env.branch)
            loaded_nodes.append(wrapped_node)
        return loaded_nodes


def get_provisioner(provisioner_name):
    """
    This will return an instance of the correct provisioner class
    :param provisioner_name: The name of the provisioner
    :type provisioner_name: str
    :rtype: Provisioner
    """

    try:
        identifier = getattr(sys.modules['monster'].provisioners,
                             provisioner_name)
    except AttributeError:
        print(traceback.print_exc())
        logger.error("The provisioner \"{0}\" was not found."
                     .format(provisioner_name))
        exit(1)
    else:
        return module_classes(identifier)[provisioner_name]()