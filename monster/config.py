"""Gathers application config"""

from os.path import dirname, join
from yaml import load
from collections import defaultdict


class Config(object):
    """Application config object"""
    def __init__(self, config, secret_path=None):
        template_path = join(dirname(dirname(__file__)), config)
        with open(template_path, 'r') as template:
            self.config = defaultdict(None, load(template.read()))

        if secret_path:
            with open(secret_path, 'r') as secret:
                self.config['secrets'] = load(secret.read())

    def __getitem__(self, name):
        return self.config[name]
