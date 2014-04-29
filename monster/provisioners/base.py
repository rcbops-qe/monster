import logging


logger = logging.getLogger(__name__)


class Provisioner(object):
    """Provisioner class template.
    Enforce implementation of provision and destroy_node and naming convention.
    """

    nodes = []

    def __repr__(self):
        return self.__class__.__name__.lower()

    def provision(self, template, deployment):
        """Provisions nodes.
        :param template: template for cluster
        :type template: dict
        :param deployment: Deployment to provision for
        :type deployment: Deployment
        :rtype: list (chef.Node)
        """
        raise NotImplementedError

    def post_provision(self, node):
        """Tasks to be done after a node is provisioned.
        :param node: Node object to be tasked
        :type node: nodes.BaseNodeWrapper
        """
        pass

    def destroy_node(self, node):
        """Destroys node.
        :param node: node to destroy
        :type node: nodes.BaseNodeWrapper
        """
        raise NotImplementedError

    def power_down(self, node):
        """Turns a node off.
        :param node: node to power off
        :type node: nodes.BaseNodeWrapper
        """
        raise NotImplementedError

    def power_up(self, node):
        """Turns a node on.
        :param node: node to power on
        :type node: nodes.BaseNodeWrapper
        """
        raise NotImplementedError

    def reload_node_list(self, node_list, api):
        raise NotImplementedError

    def build_nodes(self, template, deployment, node_wrapper):
        """
        :param node_wrapper: Module that contains a wrap_node function.
        See chef_node_wrapper.wrap_node for an example.
        :type node_wrapper: module
        """
        product = template['product']
        nodes_to_wrap = self.provision(template, deployment)

        built_nodes = []
        for node in nodes_to_wrap:
            wrapped_node = node_wrapper.wrap_node(node=node, product=product,
                                                  environment=
                                                  deployment.environment,
                                                  deployment=deployment,
                                                  provisioner=self,
                                                  branch=deployment.branch)
            self.post_provision(wrapped_node)
            built_nodes.append(wrapped_node)

        for node, features in zip(built_nodes, template['nodes']):
            node.add_features(features)

        return built_nodes

    def load_nodes(self, env, deployment, node_wrapper):
        """
        :param node_wrapper: Module that contains a wrap_node function
        See chef_node_wrapper.wrap_node for an example.
        :type node_wrapper: module
        """
        nodes_to_load = self.reload_node_list(env.nodes, env.local_api)

        loaded_nodes = []
        for node in nodes_to_load:
            if not node.exists:
                logger.error("Non-existent chef node: {0}".format(node.name))
                continue
            wrapped_node = node_wrapper.wrap_node(node=node,
                                                  product=env.product,
                                                  environment=env,
                                                  deployment=deployment,
                                                  provisioner=self,
                                                  branch=env.branch)
            loaded_nodes.append(wrapped_node)
        return loaded_nodes
