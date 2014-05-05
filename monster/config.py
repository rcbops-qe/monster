import logging

import pkg_resources

from yaml import load
from collections import defaultdict
from monster.template import Template

import database

logger = logging.getLogger(__name__)
db = database.get_connection()


def fetch_config(name):
    """Returns a dictionary with the deployment's config loaded in it.
    :param name: name of your deployment
    """
    config, secret = db.hmget(name, ['config', 'secret'])

    with open(_config_path(config), 'r') as f:
        config = defaultdict(None, load(f.read()))

    with open(_secret_path(secret), 'r') as f:
        config['secrets'] = load(f.read())

    return config


def fetch_template(name):
    """Returns a dictionary with the deployment's template loaded in it.
    :param name of deployment
    :return: Template
    """
    branch, template = db.hmget(name, ['branch', 'template'])

    with open(_template_path(branch), 'r') as f:
        template = Template(load(f.read())[template])

    return template


def _config_path(config):
    return pkg_resources.resource_filename(__name__, 'configs/%s' % config)


def _secret_path(secret):
    return pkg_resources.resource_filename(__name__, secret)


def _template_path(branch):
    if branch == "master":
        template_file = "default"
    else:
        template_file = branch.lstrip('v').rstrip("rc").replace('.', '_')
    return "templates/{0}.yaml".format(template_file)
