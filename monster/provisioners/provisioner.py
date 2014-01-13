class Provisioner(object):
    """
    Provisioner class template

    Enforce implementation of provsision and destroy_node and naming convention
    """

    def __repr__(self):
        return self.__class__.__name__.lower()

    def provision(self, template, deployment):
        """
        Provisions nodes
        :param template: template for cluster
        :type template: dict
        :param deployment: Deployment to provision for
        :type deployment: Deployment
        :rtype: list
        """
        raise NotImplementedError

    def post_provision(self, node):
        """
        Tasks to be done after a node is provisioned
        :param node: Node object to be tasked
        :type node: Monster.Node
        """
        pass

    def destroy_node(self, node):
        """
        Destroys node
        :param node: node to destroy
        :type node: Monster.Node
        """
        raise NotImplementedError

    def power_down(self, node):
        """
        Turns a node off
        :param node: node to power off
        :type node: Monster.Node
        """
        raise NotImplementedError

    def power_up(self, node):
        """
        Turns a node on
        :param node: node to power on
        :type node: Monster.Node
        """
        raise NotImplementedError
