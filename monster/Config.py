"""Gathers application config"""

import os
from monster import util
from yaml import load


class Config(object):
    """Application config object"""
    def __init__(self, file=None):
        if not file:
            file = os.path.join(os.path.dirname(__file__),
                                os.pardir,
                                'config.yaml')
        f = open(file)
        self.config = load(f)
        # Add secrets to config object
        secret_file = os.path.join(os.path.dirname(file), "secret.yaml")
        secrets = load(secret_file)
        self.config['secrets'] = secrets

    def __getitem__(self, name):
        return self.config[name]
