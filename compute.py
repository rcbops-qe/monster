#! /usr/bin/env python

"""
Command Line interface for Building Openstack clusters
"""
import sys
import argh
import traceback
import webbrowser
from monster import util
from monster.provisioners import provisioner as provisioners
from monster.config import Config
from monster.deployments.chef_deployment import ChefDeployment
from monster.features.deployment_features import Tempest


def build(name="build", template="precise-default", branch="master",
          config=None, destroy=False, dry=False,
          log=None, log_level="INFO", provisioner="razor", test=False):
    """
    Builds an OpenStack Cluster
    """
    _set_log(log, log_level)

    # Magic to get the template location from the branch
    if branch == "master":
        template_file = "default"
    else:
        temp_branch = branch.lstrip('v')
        if "rc" in temp_branch:
            template_file = str(branch).rstrip("rc").replace('.', '_')

    # provisiong deployment
    util.config = Config(config)
    class_name = util.config["provisioners"][provisioner]
    cprovisioner = util.module_classes(provisioners)[class_name]()
    deployment = ChefDeployment.fromfile(name, template, branch,
                                         cprovisioner, template_file)
    if dry:
        # build environment
        try:
            deployment.update_environment()
        except Exception:
            util.logger.error(traceback.print_exc())
            if destroy:
                deployment.destroy()
            sys.exit(1)

    else:
        if test:
            tempest = Tempest(deployment, None)
            deployment.features.append(tempest)

        util.logger.info(deployment)
        # build deployment
        try:
            deployment.build()
        except Exception:
            util.logger.error(traceback.print_exc())
            if destroy:
                deployment.destroy()
            sys.exit(1)

    util.logger.info(deployment)

    if destroy:
        deployment.destroy()


def upgrade(name='precise-default', upgrade_branch='v4.1.3rc',
            config=None, log=None, log_level="INFO"):
    """
    Upgrades a current deployment to the new branch / tag
    """
    _set_log(log, log_level)
    deployment = _load(name, config)
    util.logger.info(deployment)
    deployment.upgrade(upgrade_branch)


def destroy(name="precise-default", config=None, log=None, log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="build", config=None, log=None,
         log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    tempest = Tempest(deployment, None)
    tempest.pre_configure()
    next(deployment.search_role("controller")).run()
    tempest.apply_feature()
    tempest.post_configure()


def artifact(name="build", config=None, log=None,
             log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    deployment.artifact()


def openrc(name="build", config=None, log=None,
           log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    deployment.openrc()


def horizon(name="build", config=None, log=None,
            log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config)
    ip = deployment.horizon_ip()
    url = "https://%s" % ip
    webbrowser.open_new_tab(url)


def show(name="build", config=None, log=None,
         log_level="INFO"):
    _set_log(log, log_level)
    # load deployment and source openrc
    deployment = _load(name, config)
    util.logger.info(str(deployment))


def _load(name="build", config=None):
    # load deployment and source openrc
    util.config = Config(config)
    return ChefDeployment.from_chef_environment(name)


def _set_log(log, log_level):
    # set log level and file
    util.set_log_level(log_level)
    if log:
        util.log_to_file(log)


if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy, openrc, horizon, show, test, upgrade])
    parser.dispatch()
