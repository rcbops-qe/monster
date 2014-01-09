
class Provisioner(object):
    """
    Provisioner class template

    Enforce implementation of provsision and destroy_node and naming convention
    """

    def __str__(self):
        return self.__class__.__name__.lower()

    def short_name(self):
        """
        Converts to short hand name
        :rtype: string
        """
        provisioners = util.config['provisioners']
        return {value: key for key, value in provisioners.items()}[str(self)]

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
        :type node: Node
        """
        raise NotImplementedError
