#! /usr/bin/env python

"""
Command-line interface for building OpenStack clusters
"""

from monster import util
from tools.compute_decorators import __log
from tools.compute_decorators import __load_deployment
from tools.compute_decorators import __build_deployment
from tools.compute_decorators import __provision_for_deployment

# try:
import os
import traceback
import webbrowser
from compute_cli import CLI
from monster.tests.utils import TestUtil
#
# except ImportError as error:
#     util.logger.error("There was an import error when trying to load '{0}' "
#                       "This may be resolved if you load the monster virtual"
#                       " environment with the command \"source .venv/bin/"
#                       "activate\"".format(error.message[16:]))
#    exit(1)
if 'monster' not in os.environ.get('VIRTUAL_ENV', ''):
    util.logger.warning("You are not using the virtual environment! We "
                        "cannot guarantee that your monster will be well"
                        "-behaved.  To load the virtual environment, use "
                        "the command \"source .venv/bin/activate\"")



@__log
@__provision_for_deployment
@__build_deployment
def build(deployment, dry):
    """
    Builds an OpenStack Cluster
    """
    if dry:
        try:
            deployment.update_environment()
        except Exception: # are you kidding me???
            error = traceback.print_exc()
            util.logger.error(error)
            exit(1)
    else:
        util.logger.info(deployment)
        try:
            deployment.build()
        except Exception:
            error = traceback.print_exc()
            util.logger.error(error)
            exit(1)

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
def upgrade(deployment, args): #do we really want to set this default (no!!)
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
    url = "https://{0}".format(ip)  # i don't think this will work
    webbrowser.open_new_tab(url)


@__log
@__load_deployment
def show(deployment, args):
    """
    Shows details about an OpenStack deployment
    """
    util.logger.info(str(deployment))

# is artifact supposed to be in the CLI?
args=CLI.parser({'build':build,'destroy':destroy,'horizon':horizon,
                 'openrc':openrc,'retrofit':retrofit,'show':show,
                 'test':test,'tmux':tmux,'upgrade':upgrade}).parse_args()

if __name__ == "__main__":
        args.func(args)
