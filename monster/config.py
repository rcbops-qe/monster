"""Gathers application config"""

import os
from yaml import load
from collections import defaultdict


class Config(object):
    """Application config object"""
    def __init__(self, file=None, secret_path=None):
        if not file:
            file = os.path.join(os.path.dirname(__file__),
                                os.pardir,
                                'config.yaml')
            secret_path = secret_path or os.path.join(os.path.dirname(file),
                                                      "secret.yaml")

        f = open(file)
        self.config = defaultdict(None, load(f))

        if secret_path:
            secret_file = open(secret_path)
            secrets = load(secret_file)
            self.config['secrets'] = secrets

    def __getitem__(self, name):
        return self.config[name]
