from monster import util
from monster.orchestrator.chef_deployment_orchestrator import \
    ChefDeploymentOrchestrator


def get_orchestrator(orchestrator_name):
    if orchestrator_name == "chef":
        return ChefDeploymentOrchestrator()
    else:
        util.logger.exception("Orchestrator %s not found." % orchestrator_name)
