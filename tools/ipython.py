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
from monster.deployments.chef_deployment import Chef


def load(name, config="default.yaml"):
    """
    Load function for iPython
    """

    util.config = Config(config)
    return Chef.from_chef_environment(name)
