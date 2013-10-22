#! /usr/bin/env python

""" Command Line interface for Building Openstack Swift clusters
"""

import sys
import argh
import logging
import traceback
from monster import util
from monster.Config import Config
from monster.Deployments import ChefRazorDeployment


def build(name="precise-swift", branch="grizzly", template_path=None,
          config=None, destroy=False, dry=False, log=None,
          log_level="INFO"):

    """ Builds an OpenStack Swift storage cluster
    """

    # Set the log level
    _set_log(log, log_level)

    # provisioning deployment
    config = Config(config)
    deployment = ChefRazorDeployment.fromfile(name,
                                              branch,
                                              config,
                                              template_path)
    util.logger.info(deployment)

    if dry:
        # build environment
        deployment.update_environment()
    else:
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

def _load(name="precise-swift", config=None):
    # load deployment and source openrc
    config = Config(config)
    deployment = ChefRazorDeployment.from_chef_environment(name, config)
    return deployment

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
