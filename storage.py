#! /usr/bin/env python

"""
Command Line interface for Building Openstack Swift clusters
"""
import sys
import traceback

import argh

from monster import util
from monster.config import Config
from monster.orchestrator.deployment_orchestrator import get_orchestrator


def build(name="autotest", template="ubuntu-default", branch="master",
          template_path=None, config="pubcloud-neutron.yaml",
          dry=False, log=None, log_level="INFO", provisioner_name="rackspace",
          secret_path=None, orchestrator_name="chef"):
    """
    Build an OpenStack Cluster
    """
    util.set_log_level(log_level)
    _load_config(config, secret_path)

    orchestrator = get_orchestrator(orchestrator_name)
    deployment = orchestrator.create_deployment_from_file(name, template,
                                                          branch,
                                                          provisioner_name)

    if dry:
        try:
            deployment.update_environment()
        except Exception:
            error = traceback.print_exc()
            util.logger.error(error)
            raise

    else:
        try:
            deployment.build()
        except Exception:
            error = traceback.print_exc()
            util.logger.error(error)
            raise

    util.logger.info(deployment)


def destroy(name="autotest", config=None, log=None, log_level="INFO"):
    """
    Tears down a OpenStack Storage cluster
    """
    util.set_log_level(log_level)
    deployment = _load(name, config)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="autotest", config=None, log=None, log_level="INFO"):
    """ Tests a OpenStack Storage cluster
    """
    raise NotImplementedError


def openrc(name="autotest", config=None, log=None, log_level="INFO"):
    """ Loads the admin environment locally for a OpenStack Storage cluster
    """

    util.set_log_level(log_level)
    deployment = _load(name, config)
    deployment.openrc()


def _load_config(config, secret_path):
    if "configs/" not in config:
        config = "configs/{}".format(config)
    util.config = Config(config, secret_file_name=secret_path)


def _load(name="autotest", config="config.yaml", secret_path=None,
          orchestrator_name="chef"):
    # Load deployment and source openrc
    _load_config(config, secret_path)
    orchestrator = get_orchestrator(orchestrator_name)
    deployment = orchestrator.load_deployment_from_name(name)
    return deployment


# Main
if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy, openrc])
    parser.dispatch()
