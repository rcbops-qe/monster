#! /usr/bin/env python

""" Command Line interface for Building Openstack Swift clusters
"""
import argh
import sys

from monster import util
from monster.config import Config
from monster.deployments.chef_deployment import Chef
from monster.provisioners import provisioner as provisioners


def build(name="autotest", branch="master", provisioner="rackspace",
          template_path=None, config=None, destroy=False,
          dry=False, log=None, log_level="INFO"):

    """ Builds an OpenStack Swift storage cluster
    """
    util.set_log_level(log_level)

    # provisiong deployment
    util.config = Config(config)
    class_name = util.config["provisioners"][provisioner]
    cprovisioner = util.module_classes(provisioners)[class_name]()
    deployment = Chef.fromfile(name, branch, cprovisioner, template_path)
    if dry:
        # build environment
        try:
            deployment.update_environment()
        except Exception:
            logger.error("Unable to update environment", exc_info=True)
            deployment.destroy()
            sys.exit(1)

    else:
        logger.info(deployment)
        # build deployment
        try:
            deployment.build()
        except Exception:
            logger.error("Unable to build deployment", exc_info=True)
            deployment.destroy()
            sys.exit(1)

    logger.info(deployment)
    if destroy:
        deployment.destroy()


def destroy(name="autotest", config=None, log=None, log_level="INFO"):
    """ Tears down a OpenStack Storage cluster
    """

    util.set_log_level(log_level)
    deployment = _load(name, config)
    logger.info(deployment)
    deployment.destroy()


def test(name="autotest", config=None, log=None, log_level="INFO"):
    """ Tests a OpenStack Storage cluster
    """

    util.set_log_level(log_level)
    deployment = _load(name, config)
    deployment.test()


def openrc(name="autotest", config=None, log=None, log_level="INFO"):
    """ Loads the admin environment locally for a OpenStack Storage cluster
    """

    util.set_log_level(log_level)
    deployment = _load(name, config)
    deployment.openrc()


def load(name="autotest", config=None, log=None, log_level="INFO"):
    """ Loads a preconfigured OpenStack Storage cluster
    """

    util.set_log_level(log_level)
    # load deployment and source openrc
    deployment = _load(name, config)
    logger.info(str(deployment))


def _load(name="autotest", config=None, provisioner="razor"):
    # load deployment and source openrc
    util.config = Config(config)
    class_name = util.config["provisioners"][provisioner]
    cprovisioner = util.module_classes(provisioners)[class_name]()
    return Chef.from_chef_environment(environment=cprovisioner)


# Main
if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy, openrc, load])

    logger = util.Logger().logger_setup()

    parser.dispatch()
