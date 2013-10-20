#! /usr/bin/env python

"""
Command Line interface for Building Openstack clusters
"""

import sys
import argh
import traceback
from monster import util
from monster.Config import Config
from monster.Deployments import ChefRazorDeployment


def build(name="precise-default", branch="grizzly", template_path=None,
          config=None, destroy=False, dry=False, log=None,
          log_level="INFO"):
    """
    Builds an OpenStack Cluster
    """
    # set log level and file
    util.set_log_level(log_level)
    if log:
        util.log_to_file(log)

    # provisiong deployment
    config = Config(config)
    deployment = ChefRazorDeployment.fromfile(name, branch, config,
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


def destroy(name="precise-default", config=None, log=None, log_level="INFO"):
    # set log level and file
    util.set_log_level(log_level)
    if log:
        util.log_to_file(log)

    # load deployment and destroy
    config = Config(config)
    deployment = ChefRazorDeployment.from_chef_environment(name, config)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="precise-default", config=None, log=None, log_level="INFO"):
    util.set_log_level(log_level)
    if log:
        util.log_to_file(log)
    config = Config(config)
    deployment = ChefRazorDeployment.from_chef_environment(name, config)
    deployment.test()


if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy])
    parser.dispatch()
