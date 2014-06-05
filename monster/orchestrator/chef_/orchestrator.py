import logging

import chef
import monster.orchestrator.base as base

from monster.environments.chef_.environment import Environment

logger = logging.getLogger(__name__)
local_api = chef.autoconfigure()


class Orchestrator(base.Orchestrator):

    def create_deployment_from_file(self, name):
        raise NotImplementedError()


    def get_env(self, name):
        """Returns a new deployment given a deployment template at path.
        :param name: name for the deployment
        :type name: str
        :rtype: Deployment
        """
        return Environment(name, local_api)

    def already_has_node(self, name):
        return False


def chef_instance(self, node):
    """Builds an instance with desired specs and initializes it with Chef.
    :param node: node to build chef instance for
    :type node: monster.nodes.chef_.node.Node
    :rtype: chef.Node
    """
    chef_node = chef.Node(node.name, api=node.environment.local_api)
    chef_node.chef_environment = node.environment.name
    chef_node['in_use'] = "provisioning"
    chef_node['ipaddress'] = node.ipaddress
    chef_node['password'] = node.password
    chef_node['uuid'] = node.uuid
    chef_node['current_user'] = node.user
    chef_node.save()
    return chef_node
