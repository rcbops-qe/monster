"""Loads deployments in iPython.

Use:
1. Start ipython in top monster directory
2. from tools.ipython import load
3. deployment = load("deployment_name", "config_file")
"""

import monster.active
import monster.data.data as data
import monster.orchestrator.chef_.orchestrator as chef_orchestrator


def load(name):
    """Helper function for loading a deployment object in iPython."""
    monster.active.config = data.fetch_config(name)
    return chef_orchestrator.Orchestrator().load_deployment_from_name(name)
