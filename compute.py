#! /usr/bin/env python

"""
Command Line interface for Building Openstack clusters
"""
import sys
import argh
import traceback
import webbrowser
from monster import util
from monster.config import Config
from monster.tests.tempest import Tempest
from monster.tests.ha import HA_Test
from monster.provisioners.util import get_provisioner
from monster.deployments.chef_deployment import Chef as MonsterChefDeployment


def build(name="build", template="precise-default", branch="master",
          config=None, destroy=False, dry=False, log=None, log_level="INFO",
          provisioner="razor", test=False, secret_path=None):
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
            template_file = temp_branch.rstrip("rc").replace('.', '_')
        else:
            template_file = temp_branch.replace('.', '_')

    # provisiong deployment
    util.config = Config(config, secret_path=secret_path)
    cprovisioner = get_provisioner(provisioner)
    deployment = MonsterChefDeployment.fromfile(
        name, template, branch, cprovisioner, template_file)
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

    if test:
        try:
            Tempest(deployment).test()
        except Exception:
            util.logger.error(traceback.print_exc())
            if destroy:
                deployment.destroy()
            sys.exit(1)

    if destroy:
        deployment.destroy()


def upgrade(name='precise-default', upgrade_branch='v4.1.3rc',
            config=None, log=None, log_level="INFO", secret_path=None):
    """
    Upgrades a current deployment to the new branch / tag
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    util.logger.info(deployment)
    deployment.upgrade(upgrade_branch)


def destroy(name="precise-default", config=None, log=None, log_level="INFO",
            secret_path=None):
    """
    Destroys an existing OpenStack deployment
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="build", config=None, log=None, log_level="INFO",
         secret_path=None):
    """
    Tests an openstack deployment
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    tempest = Tempest(deployment)
    tempest.test()

    if "ha" in deployment.feature_names:
        ha = HA_Test(deployment)
        ha.test()


def artifact(name="build", config=None, log=None, secret_path=None,
             log_level="INFO"):
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    deployment.artifact()


def openrc(name="build", config=None, log=None, secret_path=None,
           log_level="INFO"):
    """
    Loads OpenStack credentials into shell env
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    deployment.openrc()


def tmux(name="build", config=None, log=None, secret_path=None,
         log_level="INFO"):
    """
    Loads OpenStack nodes into new tmux session
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    deployment.tmux()


def horizon(name="build", config=None, log=None, secret_path=None,
            log_level="INFO"):
    """
    Opens horizon in a browser tab
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    ip = deployment.horizon_ip()
    url = "https://%s" % ip
    webbrowser.open_new_tab(url)


def show(name="build", config=None, log=None, secret_path=None,
         log_level="INFO"):
    """
    Shows details about and OpenStack deployment
    """
    _set_log(log, log_level)
    # load deployment and source openrc
    deployment = _load(name, config, secret_path)
    util.logger.info(str(deployment))


def _load(name="build", config=None, secret_path=None):
    # load deployment and source openrc
    util.config = Config(config, secret_path=secret_path)
    return MonsterChefDeployment.from_chef_environment(name)


def _set_log(log, log_level):
    # set log level and file
    util.set_log_level(log_level)
    if log:
        util.log_to_file(log)


if __name__ == "__main__":
    parser = argh.ArghParser()
    parser.add_commands([build, destroy, openrc, horizon, show, test, upgrade,
                         tmux])
    parser.dispatch()
