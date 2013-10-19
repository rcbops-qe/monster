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
          config=None, destroy=False, dry=False):
    """
    Builds an OpenStack Cluster
    """
    config = Config(config)
    deployment = ChefRazorDeployment.fromfile(name,
                                              branch,
                                              config,
                                              template_path)
    util.logger.info(deployment)

    if dry:
        deployment.update_environment()
    else:
        try:
            deployment.build()
        except Exception:
            util.logger.error(traceback.print_exc())
            deployment.destroy()
            sys.exit(1)

    util.logger.info(deployment)
    if destroy:
        deployment.destroy()


def destroy(name="precise-default", config=None):
    config = Config(config)
    deployment = ChefRazorDeployment.from_chef_environment(name, config)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="precise-default", config=None):
    config = Config(config)
    deployment = ChefRazorDeployment.from_chef_environment(name, config)
    deployment.test()


if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy])
    parser.dispatch()
