from monster import util
from monster.config import Config
from monster.deployments.chef_deployment import Chef

def load(name):
    """
    Load function for iPython
    """

    util.config = Config()
    return Chef.from_chef_environment(name)
