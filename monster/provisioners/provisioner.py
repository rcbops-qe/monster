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

    def build_nodes(self, template, deployment, node_wrapper_factory):
        product = template.fetch('product')
        nodes_to_wrap = self.provision(template, deployment)
        built_nodes = []
        for node in nodes_to_wrap:
            wrapped_node = node_wrapper_factory.wrap_node(
                node, product, deployment.environment, deployment,
                provisioner=self, branch=deployment.branch)
            self.post_provision(wrapped_node)
            built_nodes.append(wrapped_node)
        return built_nodes