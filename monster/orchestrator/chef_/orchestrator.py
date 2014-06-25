import logging

import chef
import monster.orchestrator.base as base
import monster.active as active

from monster.environments.chef_.environment import Environment

logger = logging.getLogger(__name__)


def local_api():
    try:
        knife_override = active.config['secrets']['chef']['knife']
        logger.debug("Using knife.rb found at {}".format(knife_override))
        return chef.autoconfigure(knife_override)
    except KeyError:
        return chef.autoconfigure()


class Orchestrator(base.Orchestrator):
    def create_deployment_from_file(self, name):
        raise NotImplementedError()

    def get_env(self, name):
        """Returns a new deployment given a deployment template at path.
        :param name: name for the deployment
        :type name: str
        :rtype: Deployment
        """
        return Environment(name, local_api())
