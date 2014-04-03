#! /usr/bin/env python

"""
Command Line interface for Building Openstack Swift clusters
"""
import sys
import argh
import traceback

from monster import util
from monster.config import Config
from monster.deployments.orchestrator import Orchestrator
from monster.provisioners import provisioner as provisioners


def build(name="autotest", branch="master", provisioner="rackspace",
          template_path=None, config=None, destroy=False,
          dry=False, log=None, log_level="INFO"):
    """
    Builds an OpenStack Swift storage cluster
    """
    util.set_log_level(log_level)

    # provision deployment
    util.config = Config(config)
    class_name = util.config["provisioners"][provisioner]
    cprovisioner = util.module_classes(provisioners)[class_name]()
    deployment = Orchestrator.get_deployment_from_file(name, branch,
                                                       cprovisioner,
                                                       template_path)
    if dry:
        # build environment
        try:
            deployment.update_environment()
        except Exception:
            util.logger.error(traceback.print_exc())
            deployment.destroy()
            sys.exit(1)

    else:
        util.logger.info(deployment)
        # build deployment
        try:
            deployment.build()
        except Exception:
            util.logger.error(traceback.print_exc())
            deployment.destroy()
            sys.exit(1)

    util.logger.info(deployment)
    if destroy:
        deployment.destroy()


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
    util.logger.info(str(deployment))


def _load(name="autotest", config=None, provisioner="razor"):
    # load deployment and source openrc
    util.config = Config(config)
    class_name = util.config["provisioners"][provisioner]
    cprovisioner = util.module_classes(provisioners)[class_name]()
    return Orchestrator.get_deployment_from_chef_env(environment=cprovisioner)


# Main
if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy, openrc, load])
    parser.dispatch()
