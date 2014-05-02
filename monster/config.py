import logging

import pkg_resources

from yaml import load
from collections import defaultdict
from monster.template import Template

logger = logging.getLogger(__name__)


def fetch_config(config, secret=None):
    """Returns a dictionary with the deployment's config loaded in it.
    :param config: configuration files, stored in configs directory.
    :param secret: secret path, stored in project root.
    """
    template_path = pkg_resources.resource_filename(__name__, config)
    with open(template_path, 'r') as template:
        config = defaultdict(None, load(template.read()))

    secret = secret or "secret.yaml"
    secret_path = pkg_resources.resource_filename(__name__, secret)
    with open(secret_path, 'r') as secret:
        config['secrets'] = load(secret.read())
    return config


def fetch_template(template_name, branch):
    """Returns a dictionary with the deployment's template loaded in it.
    :param template_name
    :param branch
    :return: Template
    """
    if branch == "master":
        template_file = "default"
    else:
        template_file = branch.lstrip('v').rstrip("rc").replace('.', '_')
    template_path = "templates/{0}.yaml".format(template_file)

    try:
        template = Template(fetch_config(template_path)[template_name])
    except KeyError:
        logger.critical("Looking for the template {0} in the file: "
                        "\n{1}\n The key was not found!"
                        .format(template_file, template_path))
        exit(1)
    else:
        return template
