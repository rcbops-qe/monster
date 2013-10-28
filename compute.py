#! /usr/bin/env python

"""
Command Line interface for Building Openstack clusters
"""
import sys
import traceback
import webbrowser

import argh

from monster import util
from monster.provisioners import chef_razor_provisioner
from monster.config import Config
from monster.deployments.chef_deployment import ChefDeployment


def build(name="precise-default", branch="grizzly", template_path=None,
          config=None, destroy=False, dry=False, log=None,
          log_level="INFO", provisioner="razor"):
    """
    Builds an OpenStack Cluster
    """
    _set_log(log, log_level)

    # provisiong deployment
    config = Config(config)
    deployment = ChefDeployment.fromfile(name, branch, config, template_path)
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


def destroy(name="precise-default", config=None, log=None, log_level="INFO",
            provisioner="razor"):
    _set_log(log, log_level)
    deployment = _load(name, config, provisioner)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="precise-default", config=None, log=None, log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    deployment.test()


def openrc(name="precise-default", config=None, log=None, log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    deployment.openrc()


def horizon(name="precise-default", config=None, log=None, log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    ip = deployment.horizon_ip()
    url = "https://%s" % ip
    webbrowser.open_new_tab(url)


def show(name="precise-default", config=None, log=None, log_level="INFO"):
    _set_log(log, log_level)
    # load deployment and source openrc
    deployment = _load(name, config)
    util.logger.info(str(deployment))


def _load(name="precise-default", config=None, provisioner="razor"):
    # load deployment and source openrc
    config = Config(config)
    class_name = config["provisioners"][provisioner]
    class_def = util.module_classes(chef_razor_provisioner)[class_name]
    razor_ip = config['razor']['ip']
    provisioner = class_def(razor_ip)
    return ChefDeployment.from_chef_environment(name, config,
                                                provisioner=provisioner)


def _set_log(log, log_level):
    # set log level and file
    util.set_log_level(log_level)
    if log:
        util.log_to_file(log)


if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy, openrc, horizon, show])
    parser.dispatch()
