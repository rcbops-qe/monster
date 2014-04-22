"""Gathers application config"""

import os

from monster import util
from yaml import load
from collections import defaultdict
from monster.template import Template


class Config(object):
    """Application config object"""
    def __init__(self, template_path_from_project_root=None,
                 secret_file_name=None):
        secret_path = secret_file_name or os.path.join(
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
            logger.critical("Looking for the template {0} in the file: "
                                 "\n{1}\n The key was not found!"
                                 .format(template_file, path))
            exit(1)
        else:
            return template
