#! /usr/bin/env python

"""
Command-line interface for building OpenStack clusters
"""

import os
from monster import util

logger = util.get_logger("{0}.log".format(__name__))

if 'monster' not in os.environ.get('VIRTUAL_ENV', ''):
    logger.warning("You are not using the virtual environment! We "
                   "cannot guarantee that your monster will be well"
                   "-behaved.  To load the virtual environment, use "
                   "the command \"source .venv/bin/activate\"")

import webbrowser
from compute_cli import CLI
from monster.tests.utils import TestUtil
from tools.compute_decorators import __load_deployment
from tools.compute_decorators import __build_deployment
from tools.compute_decorators import __provision_for_deployment



@__provision_for_deployment
@__build_deployment
def build(deployment, args):
    """
    Builds an OpenStack Cluster
    """
    if args.dry:
        deployment.update_environment()
    else:
        deployment.build()

    logger.info(deployment)


@__load_deployment
def test(deployment, args):
    """
    Tests an OpenStack deployment
    """
    test_util = TestUtil(deployment, args)

    if args.all or args.ha:
        test_util.runHA()
    if args.all or args.tempest:
        test_util.runTempest()
    test_util.report()


@__load_deployment
def retrofit(deployment, retro_branch='dev', ovs_bridge='br-eth1',
             x_bridge='lxb-mgmt', iface='eth0', del_port=None):
    """
    Retrofits an OpenStack deployment
    """
    deployment.retrofit(retro_branch, ovs_bridge, x_bridge, iface, del_port)


@__load_deployment
def upgrade(deployment, args):
    """
    Upgrades a current deployment to the new branch / tag
    """
    deployment.upgrade(args['upgrade_branch'])


@__load_deployment
def destroy(deployment, args):
    """
    Destroys an existing OpenStack deployment
    """
    deployment.destroy()


@__load_deployment
def artifact(deployment, args):
    """
    Artifacts a deployment (configs / running services)
    """
    deployment.artifact()


@__load_deployment
def openrc(deployment, args):
    """
    Loads OpenStack credentials into shell env
    """
    deployment.openrc()


@__load_deployment
def tmux(deployment, args):
    """
    Loads OpenStack nodes into new tmux session
    """
    deployment.tmux()


@__load_deployment
def horizon(deployment, args):
    """
    Opens Horizon in a browser tab
    """
    ip = deployment.horizon_ip()
    url = "https://{0}".format(ip)
    webbrowser.open_new_tab(url)


@__load_deployment
def show(deployment, args):
    """
    Shows details about an OpenStack deployment
    """
    util.set_log_level(logger, "INFO")
    logger.info(str(deployment))

# is artifact supposed to be in the CLI?
args = CLI.parser(
    {'build': build, 'destroy': destroy, 'horizon': horizon, 'openrc': openrc,
     'retrofit': retrofit, 'show': show, 'test': test, 'tmux': tmux,
     'upgrade': upgrade}).parse_args()

if __name__ == "__main__":
    args.func(args)
