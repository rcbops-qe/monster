import logging

import chef

import monster.database as database
import monster.deployments.rpcs.deployment as rpcs
import monster.orchestrator.base as base

from monster.environments.chef_.environment import Environment

logger = logging.getLogger(__name__)
local_api = chef.autoconfigure()


class Orchestrator(base.Orchestrator):

    def create_deployment_from_file(self, name):
        """Returns a new deployment given a deployment template at path.
        :param name: name for the deployment
        :type name: str
        :rtype: Deployment
        """

        logger.info("Building deployment object for {0}".format(name))

        if chef.Environment(name, api=local_api).exists:
            logger.info("Using previous deployment:{0}".format(name))
            return database.load_deployment(name)

        environment = Environment(name, local_api)

        return rpcs.Deployment(name, environment)
