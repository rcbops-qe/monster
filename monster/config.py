"""Gathers application config"""

import logging

from os import path
from yaml import load
from collections import defaultdict
from monster.template import Template


logger = logging.getLogger(__name__)


class Config(object):
    def __init__(self, config, secret=None):
        """Initializes application config object.
        :param config: configuration files, stored in configs directory.
        :param secret: secret path, stored in project root.
        """
        template_path = path.join(path.dirname(path.dirname(__file__)), config)
        with open(template_path, 'r') as template:
            self.config = defaultdict(None, load(template.read()))

        secret_path = secret or "secret.yaml"
        with open(secret_path, 'r') as secret:
            self.config['secrets'] = load(secret.read())

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

        template_path = path.join(path.dirname(__file__), path.pardir,
                                  "templates/{0}.yaml".format(template_file))

        try:
            template = Template(Config(template_path)[template_name])
        except KeyError:
            logger.critical("Looking for the template {0} in the file: "
                            "\n{1}\n The key was not found!"
                            .format(template_file, template_path))
            exit(1)
        else:
            return template
