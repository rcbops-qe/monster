"""Gathers application config"""

import os
from yaml import load
from collections import defaultdict


class Config(object):
    """Application config object"""
    def __init__(self, secret_path, template_path_from_project_root=None,
                 secret_file_name=None):
        secret_path = secret_path or os.path.join(
            os.path.dirname(os.path.dirname(__file__)), "secret.yaml")

        template_path = os.path.join(os.path.dirname(os.path.dirname(
            __file__)), template_path_from_project_root)

        template_file = open(template_path)
        self.config = defaultdict(None, load(template_file))

        secret_file = open(secret_path)
        secrets = load(secret_file)
        self.config['secrets'] = secrets

    def __getitem__(self, name):
        return self.config[name]
