"""Gathers application config"""

import os
from yaml import load
from collections import defaultdict


class Config(object):
    """Application config object"""
    def __init__(self, template_file_name="config.yaml",
                 secret_file_name="secret.yaml"):
        secret_path = secret_file_name or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), secret_file_name)

        template_path = os.path.join(os.path.dirname(os.path.dirname(
            __file__)), 'config/{0}'.format(template_file_name))

        template_file = open(template_path)
        self.config = defaultdict(None, load(template_file))

        secret_file = open(secret_path)
        secrets = load(secret_file)
        self.config['secrets'] = secrets

    def __getitem__(self, name):
        return self.config[name]
