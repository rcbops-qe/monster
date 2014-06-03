import logging

import chef
from monster.data.data import load_deployment

import monster.deployments.rpcs.deployment as rpcs
import monster.orchestrator.base as base
import monster.active as active

from monster.environments.chef_.environment import Environment

logger = logging.getLogger(__name__)


class Orchestrator(base.Orchestrator):

    def create_deployment_from_file(self, name):
        """Returns a new deployment given a deployment template at path.
        :param name: name for the deployment
        :type name: str
        :rtype: Deployment
        """

        logger.info("Building deployment object for {0}".format(name))

        # Try to load the knife config from the configured path
        # if there isnt a knife.rb then load the one in the
        # default path
        if active.config['secrets']['chef']['knife']:
            local_api = chef.autoconfigure(
                active.config['secrets']['chef']['knife'])
            logger.debug("Using knife.rb found at {}".format(
                active.config['secrets']['chef']['knife']))
        else:
            local_api = chef.autoconfigure()

        if chef.Environment(name, api=local_api).exists:
            logger.info("Using previous deployment:{0}".format(name))
            return load_deployment(name)

        environment = Environment(name, local_api)

        return rpcs.Deployment(name, environment)
