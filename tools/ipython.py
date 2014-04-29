"""Loads deployments in iPython.

Use:
1. Start ipython in top monster directory
2. from tools.ipython import load
3. deployment = load("deployment_name", "config_file")
"""

import monster.util
import monster.config
import monster.orchestrator.chef.orchestrator as chef_orchestrator


def load(name, config="config.yaml"):
    """Helper function for loading a deployment object in iPython."""
    monster.util.config = monster.config.fetch_config(config)
    return chef_orchestrator.Orchestrator().load_deployment_from_name(name)
