#! /usr/bin/env python

""" Command Line interface for Building Openstack Swift clusters
"""
import argh
import traceback

from monster import util
from monster.config import Config
from monster.orchestrator.util import get_orchestrator


def build(name="autotest", branch="master", provisioner_name="rackspace",
          template=None, config=None, destroy=False,
          secret_path="secret.yaml", dry=False, log=None,
          orchestrator_name="chef"):

    """ Builds an OpenStack Swift storage cluster
    """
    # provisiong deployment
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
            logger.exception(error)

    else:
        try:
            deployment.build()
        except Exception:
            error = traceback.print_exc()
            logger.exception(error)

    logger.info(deployment)

    if destroy:
        deployment.destroy()


def destroy(name="autotest", config=None, log=None):
    """ Tears down a OpenStack Storage cluster
    """
    deployment = _load(name, config)
    logger.info(deployment)
    deployment.destroy()


def test(name="autotest", config=None, log=None):
    """ Tests a OpenStack Storage cluster
    """
    deployment = _load(name, config)
    deployment.test()


def openrc(name="autotest", config=None, log=None):
    """ Loads the admin environment locally for a OpenStack Storage cluster
    """
    deployment = _load(name, config)
    deployment.openrc()


def load(name="autotest", config=None, log=None):
    """ Loads a preconfigured OpenStack Storage cluster
    """

    # load deployment and source openrc
    deployment = _load(name, config)
    logger.info(str(deployment))


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
    parser.add_commands([build, destroy, openrc, load])

    logger = util.Logger().logger_setup()

    parser.dispatch()
