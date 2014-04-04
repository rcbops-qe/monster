"""Gathers application config"""

import os

from monster import util
from yaml import load
from collections import defaultdict
from monster.template import Template


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

    @classmethod
    def fetch_template(cls, template_name, branch):
        """
        :param template_name
        :param branch
        :return: Template
        """
        if branch == "master":
            template_file = "default"
        else:
            template_file = branch.lstrip('v').rstrip("rc").replace('.', '_')

        path = os.path.join(os.path.dirname(__file__), os.pardir,
                            "templates/{0}.yaml".format(template_file))

        try:
            template = Template(Config(path)[template_name])
        except KeyError:
            util.logger.critical("Looking for the template {0} in the file: "
                                 "\n{1}\n The key was not found!"
                                 .format(template_file, path))
            exit(1)
        else:
            return template
