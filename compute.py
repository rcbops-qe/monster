#! /usr/bin/env python

"""
Command-line interface for building OpenStack clusters
"""

import os
from monster.util import Logger

logger = Logger("compute")
logger.set_log_level("INFO")


if 'monster' not in os.environ.get('VIRTUAL_ENV', ''):
    logger.warning("You are not using the virtual environment! We "
                   "cannot guarantee that your monster will be well"
                   "-behaved.  To load the virtual environment, use "
                   "the command \"source .venv/bin/activate\"")

import webbrowser
from compute_cli import CLI
from monster.tests.util import TestUtil
from tools.compute_decorators import __load_deployment
from tools.compute_decorators import __build_deployment
from tools.compute_decorators import __provision_for_deployment


@__provision_for_deployment
@__build_deployment
def build(deployment):
    """
    Builds an OpenStack Cluster
    """
    if args.dry:
        deployment.update_environment()
    else:
        deployment.build()

    logger.info(deployment)


@__load_deployment
def test(deployment, tests_to_run, iterations):
    """
    Tests an OpenStack deployment
    """
    test_util = TestUtil(deployment, iterations)
    for test in test_util.get_tests(tests_to_run):
        test()


@__load_deployment
def retrofit(deployment, retro_branch='dev', ovs_bridge='br-eth1',
             x_bridge='lxb-mgmt', iface='eth0', del_port=None):
    """
    Retrofits an OpenStack deployment
    """
    deployment.retrofit(retro_branch, ovs_bridge, x_bridge, iface, del_port)


@__load_deployment
def upgrade(deployment, upgrade_branch):
    """
    Upgrades a current deployment to the new branch / tag
    """
    deployment.upgrade(upgrade_branch)


@__load_deployment
def destroy(deployment):
    """
    Destroys an existing OpenStack deployment
    """
    deployment.destroy()


@__load_deployment
def artifact(deployment):
    """
    Artifacts a deployment (configs / running services)
    """
    deployment.artifact()


@__load_deployment
def openrc(deployment):
    """
    Loads OpenStack credentials into shell env
    """
    deployment.openrc()


@__load_deployment
def tmux(deployment):
    """
    Loads OpenStack nodes into new tmux session
    """
    deployment.tmux()


@__load_deployment
def horizon(deployment):
    """
    Opens Horizon in a browser tab
    """
    ip = deployment.horizon_ip()
    url = "https://{0}".format(ip)
    webbrowser.open_new_tab(url)


@__load_deployment
def show(deployment):
    """
    Shows details about an OpenStack deployment
    """
    logger.info(str(deployment))

# is artifact supposed to be in the CLI?
args = CLI.parser(
    {'build': build, 'destroy': destroy, 'horizon': horizon, 'openrc': openrc,
     'retrofit': retrofit, 'show': show, 'test': test, 'tmux': tmux,
     'upgrade': upgrade}).parse_args()

if __name__ == "__main__":
    #import cProfile
    #cProfile.run('args.func(args)')
    args.func(args)
