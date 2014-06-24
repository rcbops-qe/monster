import logging
import pkg_resources

from collections import defaultdict
from os import path
from sys import exit
from yaml import load

import monster.db_iface as database
from monster import active

logger = logging.getLogger(__name__)


def load_deployment(name):
    """Loads the deployment from the database.
    :rtype: monster.deployments.base.Deployment"""
    deployment = database.fetch_deployment(name)
    return deployment


def load_config(name):
    try:
        active.config = fetch_config(name)
        active.template = fetch_template(name)
        active.build_args = database.fetch_build_args(name)
    except IOError as exc:
        logger.error("Ensure correct deployment name: {0}".format(exc))
        exit(1)


def load_only_secrets(secret_path):
    active.config = {'secrets': fetch_secrets(secret_path)}


def fetch_secrets(secret):
    with open(_secret_path(secret), 'r') as f:
        secrets = load(f.read())
    return secrets


def fetch_config(name):
    """Returns a dictionary with the deployment's config loaded in it.
    :param name: name of your deployment
    """
    config, secret = database.fetch_config_params(name)

    with open(_config_path(config), 'r') as f:
        config = defaultdict(None, load(f.read()))

    config['secrets'] = fetch_secrets(secret)
    return config


def fetch_template(name):
    """Returns a dictionary with the deployment's template loaded in it.
    :param name of deployment
    """
    branch, template = database.fetch_template_params(name)

    with open(_template_path(branch), 'r') as f:
        template = load(f.read())[template]

    return template


def _config_path(config):
    return pkg_resources.resource_filename(__name__, 'configs/%s' % config)


def _secret_path(secret):
    if path.exists(path.expanduser(secret)):
        return secret
    else:
        return pkg_resources.resource_filename(__name__, secret)


def _template_path(branch):
    if branch == "master":
        template_file = "default"
    else:
        template_file = branch.lstrip('v').rstrip("rc").replace('.', '_')
    template_file = "templates/{0}.yaml".format(template_file)

    return pkg_resources.resource_filename(__name__, template_file)
