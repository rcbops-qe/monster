#! /usr/bin/env python

""" Command Line interface for Building Openstack Swift clusters
"""
import sys
import traceback

import argh

from monster import util
from monster.provisioners import provisioner as provisioners
from monster.config import Config
from monster.deployments.chef_deployment import ChefDeployment


def build(name="precise-swift", branch="master", provisioner="razor",
          template_path=None, config=None, destroy=False,
          dry=False, log=None, log_level="INFO"):

    """ Builds an OpenStack Swift storage cluster
    """

    _set_log(log, log_level)

    # provisiong deployment
    util.config = Config(config)
    class_name = util.config["provisioners"][provisioner]
    cprovisioner = util.module_classes(provisioners)[class_name]()
    deployment = ChefDeployment.fromfile(name, branch, cprovisioner,
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


def destroy(name="precise-swift", config=None, log=None, log_level="INFO"):
    """ Tears down a OpenStack Storage cluster
    """

    _set_log(log, log_level)
    deployment = _load(name, config)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="precise-swift", config=None, log=None, log_level="INFO"):
    """ Tests a OpenStack Storage cluster
    """

    _set_log(log, log_level)
    deployment = _load(name, config)
    deployment.test()


def openrc(name="precise-swift", config=None, log=None, log_level="INFO"):
    """ Loads the admin environment locally for a OpenStack Storage cluster
    """

    _set_log(log, log_level)
    deployment = _load(name, config)
    deployment.openrc()


def load(name="precise-swift", config=None, log=None, log_level="INFO"):
    """ Loads a preconfigured OpenStack Storage cluster
    """

    _set_log(log, log_level)
    # load deployment and source openrc
    deployment = _load(name, config)
    util.logger.info(str(deployment))


def _load(name="precise-swift", config=None, provisioner="razor"):
    # load deployment and source openrc
    util.config = Config(config)
    class_name = util.config["provisioners"][provisioner]
    cprovisioner = util.module_classes(provisioners)[class_name]()
    return ChefDeployment.from_chef_environment(name, provisioner=cprovisioner)


def _set_log(log, log_level):
    # set log level and file
    util.set_log_level(log_level)
    if log:
        util.log_to_file(log)

# Main
if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy, openrc, load])
    parser.dispatch()
