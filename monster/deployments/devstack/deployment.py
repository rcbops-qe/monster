import monster.deployments.base as base


class Deployment(base.Deployment):
    """Deployment mechanisms specific to a RPCS deployment using Chef as
    configuration management.
    """

    def __init__(self, name, environment, status=None, clients=None):

        """Initializes a RPCS deployment object.
        :type name: str
        :type environment: monster.environments.chef.environment.Environment
        :type status: str
        """
        raise NotImplementedError()

    def __str__(self):
        return str(self.to_dict)

    def build(self):
        """Saves deployment for restore after build."""
        raise NotImplementedError()

    def save_to_environment(self):
        """Save deployment restore attributes to chef environment."""
        raise NotImplementedError()

    def get_upgrade(self, branch_name):
        """This will return an instance of the correct upgrade class.
        :param branch_name: The name of the provisioner
        :type branch_name: str
        :rtype: monster.deployments.base.Deployment
        """
        raise NotImplementedError()

    def upgrade(self, branch_name):
        """Upgrades the deployment."""
        raise NotImplementedError()

    def update_environment(self):
        """Saves deployment for restore after update environment."""
        raise NotImplementedError()

    def destroy(self):
        """Destroys Chef Deployment."""
        raise NotImplementedError()

    def horizon(self):
        raise NotImplementedError()

    def openrc(self):
        """Opens a new shell with variables loaded for nova-client."""
        raise NotImplementedError()

    @property
    def to_dict(self):
        raise NotImplementedError()

    @property
    def openstack_clients(self):
        """Setup OpenStack clients generator for deployment."""
        raise NotImplementedError()

    @property
    def rabbitmq_mgmt_client(self):
        """Return rabbitmq management client."""
        raise NotImplementedError()

    @property
    def horizon_ip(self):
        """Returns IP of Horizon.
        :rtype: str
        """
        raise NotImplementedError()

    def wrap_node(self, node):
        raise NotImplementedError()
