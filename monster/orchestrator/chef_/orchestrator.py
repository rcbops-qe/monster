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
