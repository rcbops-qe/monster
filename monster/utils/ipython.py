"""Loads deployments in iPython.

Use:
1. Start ipython in top monster directory
2. from monster.utils.ipython import load
3. deployment = load(<deployment_name>)
"""
from monster.data import data


def load(name):
    """Helper function for loading a deployment object in iPython."""
    return data.load_deployment(name)
