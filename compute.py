#! /usr/bin/env python

"""
Command-line interface for building OpenStack clusters
"""

import os
from monster import util

if 'monster' not in os.environ.get('VIRTUAL_ENV', ''):
    util.logger.warning("You are not using the virtual environment! We "
                        "cannot guarantee that your monster will be well"
                        "-behaved.  To load the virtual environment, use "
                        "the command \"source .venv/bin/activate\"")


import webbrowser
from compute_cli import CLI
from monster.tests.utils import TestUtil
from tools.compute_decorators import __log
from tools.compute_decorators import __load_deployment
from tools.compute_decorators import __build_deployment
from tools.compute_decorators import __provision_for_deployment


@__log
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

    util.logger.info(deployment)


@__log
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


@__log
@__load_deployment
def retrofit(deployment, retro_branch='dev', ovs_bridge='br-eth1',
             x_bridge='lxb-mgmt', iface='eth0', del_port=None):
    """
    Retrofits an OpenStack deployment
    """
    deployment.retrofit(retro_branch, ovs_bridge, x_bridge, iface, del_port)


@__log
@__load_deployment
def upgrade(deployment, args):
    """
    Upgrades a current deployment to the new branch / tag
    """
    deployment.upgrade(args['upgrade_branch'])


@__log
@__load_deployment
def destroy(deployment, args):
    """
    Destroys an existing OpenStack deployment
    """
    deployment.destroy()


@__log
@__load_deployment
def artifact(deployment, args):
    """
    Artifacts a deployment (configs / running services)
    """
    deployment.artifact()


@__log
@__load_deployment
def openrc(deployment, args):
    """
    Loads OpenStack credentials into shell env
    """
    deployment.openrc()


@__log
@__load_deployment
def tmux(deployment, args):
    """
    Loads OpenStack nodes into new tmux session
    """
    deployment.tmux()


@__log
@__load_deployment
def horizon(deployment, args):
    """
    Opens Horizon in a browser tab
    """
    ip = deployment.horizon_ip()
    url = "https://{0}".format(ip)
    webbrowser.open_new_tab(url)


@__log
@__load_deployment
def show(deployment, args):
    """
    Shows details about an OpenStack deployment
    """
    util.logger.info(str(deployment))

# is artifact supposed to be in the CLI?
args = CLI.parser(
    {'build': build, 'destroy': destroy, 'horizon': horizon, 'openrc': openrc,
     'retrofit': retrofit, 'show': show, 'test': test, 'tmux': tmux,
     'upgrade': upgrade}).parse_args()

if __name__ == "__main__":
        args.func(args)
