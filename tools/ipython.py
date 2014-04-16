"""
Tool to load deployments in iPython

Use:
1. Start ipython in top monster directory
2. from tools.ipython import load
3. deployment = load("yourdep")
4. profit???
"""

from monster import util
from monster.config import Config
from monster.orchestrator.chef_deployment_orchestrator import \
    ChefDeploymentOrchestrator


def load(name, config="config.yaml"):
    """
    Load function for iPython
    """
    util.config = Config(config)
    return ChefDeploymentOrchestrator().load_deployment_from_name(name)
