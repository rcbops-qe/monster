"""Gathers application config"""

import os
from yaml import load
from collections import defaultdict


class Config(object):
    """Application config object"""
    def __init__(self, file_path=None, secret_path=None):
        secret_path = secret_path or os.path.join(os.path.dirname(__file__),
                                                  os.pardir, 'secret.yaml')
        file_path = file_path or os.path.join(os.path.dirname(__file__),
                                              os.pardir, 'config.yaml')

        with open(file_path, 'r') as f:
            secret_file = open(secret_path)
            secrets = load(secret_file)
            self.config = defaultdict(None, load(f))
            self.config['secrets'] = secrets

    def __getitem__(self, name):
        return self.config[name]
