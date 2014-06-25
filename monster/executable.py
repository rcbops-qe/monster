#! /usr/bin/env python
"""Command-line interface for building OpenStack clusters."""

import sys
import argh
import IPython

import monster.db_iface as database
import monster.deployments.rpcs.deployment as rpcs
from monster.data import data
from monster.logger import logger as monster_logger
from monster.utils.access import get_file, run_cmd
from monster.utils.color import Color
from monster.tests.ha import HATest
from monster.tests.cloudcafe import CloudCafe
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum
from monster.utils.safe_build import cleanup_on_failure
from monster.utils.status import check_monster_status


logger = monster_logger.Logger().logger_setup()


def status(secrets="secret.yaml"):
    logger.setLevel(20)
    data.load_only_secrets(secrets)
    try:
        check_monster_status()
    except:
        sys.exit(1)
    else:
        sys.exit(0)


@argh.named("rpcs")
@database.store_build_params
def rpcs_build(
        name, template="ubuntu-default", branch="master",
        config="pubcloud-neutron.yaml", provisioner="rackspace",
        orchestrator="chef", secret="secret.yaml", dry=False, log=None,
        destroy_on_failure=False):
    """Build a Rackspace Private Cloud deployment."""
    data.load_config(name)
    deployment = rpcs.Deployment(name)
    with cleanup_on_failure(deployment):
        deployment.build()
    return deployment


@database.store_build_params
def devstack(name, template="ubuntu-default", branch="master",
             config="pubcloud-neutron.yaml", provisioner="rackspace",
             orchestrator="chef", secret="secret.yaml", dry=False, log=None,
             destroy_on_failure=False):
    """Build a Devstack deployment."""
    pass


def tempest(name, iterations=1):
    """Test an OpenStack deployment."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    branch = TempestQuantum.tempest_branch(deployment.branch)
    if "grizzly" in branch:
        test_object = TempestQuantum(deployment)
    else:
        test_object = TempestNeutron(deployment)
    local = "./results/{}/".format(deployment.name)
    run_cmd("mkdir -p {}".format(local))

    for controller in deployment.controllers:
        ip, user, password = (controller.ipaddress, controller.user,
                              controller.password)
        remote = "{0}@{1}:~/*.xml".format(user, ip)
        get_file(ip, user, password, remote, local)

    for i in range(iterations):
        logger.info(Color.cyan('Tempest: running iteration {0} of {1}!'
                         .format(i + 1, iterations)))
        test_object.test()

    logger.info(Color.cyan("Tempest tests completed..."))


def ha(name, iterations=1, progress=False):
    """Test an OpenStack deployment."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    test_object = HATest(deployment, progress)
    local = "./results/{0}/".format(deployment.name)
    run_cmd("mkdir -p {}".format(local))

    for controller in deployment.controllers:
        ip, user, password = (controller.ipaddress, controller.user,
                              controller.password)
        remote = "{0}@{1}:~/*.xml".format(user, ip)
        get_file(ip, user, password, remote, local)

    for i in xrange(iterations):
        logger.info(Color.cyan('HA: running iteration {0} of {1}!'
                         .format(i + 1, iterations)))
        test_object.test(iterations)

    logger.info(Color.cyan("HA tests completed..."))


def retrofit(name='autotest', retro_branch='dev', ovs_bridge='br-eth1',
             x_bridge='lxb-mgmt', iface='eth0', del_port=None):
    """Retrofit a deployment."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    logger.info(deployment)
    deployment.retrofit(retro_branch, ovs_bridge, x_bridge, iface, del_port)


def update(name):
    """Runs package updates on all nodes in a deployment, in addition to
    running chef-client (or the equivalent) on all non-orchestrator nodes."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    deployment.update()


@database.store_upgrade_params
def upgrade(name, upgrade_branch='v4.1.3rc'):
    """Upgrade a current deployment to the new branch / tag."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    logger.info(deployment)
    deployment.upgrade(upgrade_branch)


def destroy(name):
    """Destroy an existing OpenStack deployment."""
    deployment = data.load_deployment(name)
    data.load_config(name)
    logger.info(deployment)
    deployment.destroy()
    database.remove_key(deployment.name)


def artifact(name):
    """Artifact a deployment (configs/running services)."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    deployment.artifact()


def openrc(name):
    """Export OpenStack credentials into shell environment."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    deployment.openrc()


def tmux(name):
    """Load OpenStack nodes into a new tmux session."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    deployment.tmux()


def horizon(name):
    """Open Horizon in a browser tab."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    deployment.horizon()


def show(name):
    """Show details about an OpenStack deployment."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    return deployment


def explore(name):
    """Explore a deployment in IPython."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    IPython.embed()


@argh.named("list")
def list_deployments():
    """Lists all deployments"""
    deployments = database.list_deployments()
    return '\n'.join(sorted(deployment for deployment in deployments))


def cloudcafe(cmd, name, network=None):
    """Run CloudCafe test suite against a deployment."""
    deployment = data.load_deployment(name)
    data.load_config(name)
    CloudCafe(deployment).config(cmd, network_name=network)


def add_nodes(name, compute_nodes=0, controller_nodes=0, cinder_nodes=0,
              request=None):
    """Add a node (or nodes) to an existing deployment."""
    data.load_config(name)
    deployment = data.load_deployment(name)
    node_request = request or list([['compute']] * compute_nodes +
                                   [['controller']] * controller_nodes +
                                   [['cinder']] * cinder_nodes)
    deployment.add_nodes(node_request)
    database.store(deployment)


def run():
    parser = argh.ArghParser()
    subparsers = parser.add_subparsers()

    subparsers.add_parser('status').set_defaults(function=status)

    deployment_parser = subparsers.add_parser('deployment')

    deployment_parser.add_commands([devstack, rpcs_build],
                                   namespace='build',
                                   title="Build-related commands")

    deployment_parser.add_commands([cloudcafe, ha, tempest],
                                   namespace='test',
                                   title="Test-related commands")

    deployment_parser.add_commands([list_deployments, show, update, upgrade,
                                    retrofit, add_nodes, destroy, openrc,
                                    horizon, tmux, explore])

    parser.dispatch()


if __name__ == "__main__":
    run()
