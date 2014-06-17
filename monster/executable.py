#! /usr/bin/env python
"""Command-line interface for building OpenStack clusters."""

import subprocess
import argh
import sys
from monster import active

import monster.db_iface as database
import monster.deployments.rpcs.deployment as rpcs
import monster.provisioners.rackspace.provisioner as rackspace
from monster.data import data
from monster.logger import logger as monster_logger
from monster.utils.access import get_file, check_port
from monster.utils.color import Color
from monster.tests.ha import HATest
from monster.tests.cloudcafe import CloudCafe
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum
from monster.utils.safe_build import cleanup_on_failure


logger = monster_logger.Logger().logger_setup()


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


@database.store_build_params
def devstack(name, template="ubuntu-default", branch="master",
             config="pubcloud-neutron.yaml", provisioner="rackspace",
             orchestrator="chef", secret="secret.yaml", dry=False, log=None):
    """Build a Devstack deployment."""
    pass


def tempest(name, deployment=None, iterations=1):
    """Test an OpenStack deployment."""
    if not deployment:
        deployment = data.load_deployment(name)

    branch = TempestQuantum.tempest_branch(deployment.branch)
    if "grizzly" in branch:
        test_object = TempestQuantum(deployment)
    else:
        test_object = TempestNeutron(deployment)

    env = deployment.environment.name
    local = "./results/{0}/".format(env)
    for controller in deployment.controllers:
        ip, user, password = controller.creds
        remote = "{0}@{1}:~/*.xml".format(user, ip)
        get_file(ip, user, password, remote, local)

    for i in range(iterations):
        logger.info(Color.cyan('Running iteration {0} of {1}!'
                         .format(i + 1, iterations)))

        #Prepare directory for xml files to be SCPed over
        subprocess.call(['mkdir', '-p', '{0}'.format(local)])

        if test_object:
            logger.info(Color.cyan('Running Tempest test!'))
            test_object.test()

    logger.info(Color.cyan("Tests have been completed with {0} iterations"
                           .format(iterations)))


def ha(name, deployment=None, iterations=1, progress=False):
    """Test an OpenStack deployment."""
    if not deployment:
        deployment = data.load_deployment(name)
    # if deployment.has_feature("highavailability"):

    test_object = HATest(deployment, progress)

    env = deployment.environment.name
    local = "./results/{0}/".format(env)
    for controller in deployment.controllers:
        ip, user, password = controller.creds
        remote = "{0}@{1}:~/*.xml".format(user, ip)
        get_file(ip, user, password, remote, local)

    for i in range(iterations):
        logger.info(Color.cyan('Running iteration {0} of {1}!'
                         .format(i + 1, iterations)))

        #Prepare directory for xml files to be SCPed over
        subprocess.call(['mkdir', '-p', '{0}'.format(local)])

        logger.info(Color.cyan('Running High Availability test!'))
        test_object.test(iterations)

    logger.info(Color.cyan("Tests have been completed with {0} iterations"
                           .format(iterations)))


def retrofit(name='autotest', retro_branch='dev', ovs_bridge='br-eth1',
             x_bridge='lxb-mgmt', iface='eth0', del_port=None):
    """Retrofit a deployment."""
    deployment = data.load_deployment(name)
    logger.info(deployment)
    deployment.retrofit(retro_branch, ovs_bridge, x_bridge, iface, del_port)


def update_nodes(name):
    """Runs package updates on all nodes in a deployment, in addition to
    running chef-client (or the equivalent) on all non-orchestrator nodes."""
    deployment = data.load_deployment(name)
    deployment.update()


@database.store_upgrade_params
def upgrade(name, upgrade_branch='v4.1.3rc'):
    """Upgrade a current deployment to the new branch / tag."""
    deployment = data.load_deployment(name)
    logger.info(deployment)
    deployment.upgrade(upgrade_branch)


def destroy(name):
    """Destroy an existing OpenStack deployment."""
    deployment = data.load_deployment(name)
    logger.info(deployment)
    deployment.destroy()
    database.remove_key(deployment.name)


def artifact(name):
    """Artifact a deployment (configs/running services)."""
    deployment = data.load_deployment(name)
    deployment.artifact()


def openrc(name):
    """Export OpenStack credentials into shell environment."""
    deployment = data.load_deployment(name)
    deployment.openrc()


def tmux(name):
    """Load OpenStack nodes into a new tmux session."""
    deployment = data.load_deployment(name)
    deployment.tmux()


def horizon(name):
    """Open Horizon in a browser tab."""
    deployment = data.load_deployment(name)
    deployment.horizon()


def show(name):
    """Show details about an OpenStack deployment."""
    deployment = data.load_deployment(name)
    logger.info(str(deployment))


def cloudcafe(cmd, name, network=None):
    """Run CloudCafe test suite against a deployment."""
    deployment = data.load_deployment(name)
    CloudCafe(deployment).config(cmd, network_name=network)


def add_nodes(name, compute_nodes=0, controller_nodes=0, cinder_nodes=0,
              request=None):
    """Add a node (or nodes) to an existing deployment."""
    deployment = data.load_deployment(name)
    node_request = request or list([['compute']] * compute_nodes +
                                   [['controller']] * controller_nodes +
                                   [['cinder']] * cinder_nodes)

    deployment.add_nodes(node_request)
    database.store(deployment)


def status(secrets="secret.yaml"):
    data.load_only_secrets(secrets)
    try:
        database.ping_db()
    except AssertionError:
        logger.warning("Database is not responding normally...")
        sys.exit(1)
    else:
        logger.info("Database is up!")
    try:
        rackspace.Provisioner()
    except Exception:
        logger.warning("Rackspace credentials did not authenticate.")
        sys.exit(1)
    else:
        logger.info("Rackspace credentials look good!")
    try:
        check_port(host=active.config['secrets']['razor']['ip'], port=8026)
    except KeyError:
        logger.info("No razor IP specified; Razor provisioner will not be "
                    "available.")
    except Exception:
        logger.warning("Specified Razor host did not seem responsive on port "
                       "8026. Razor provisioner will likely be unavailable.")
        sys.exit(0)
    else:
        logger.info("Razor host is up and responding on port 8026!")
    logger.info("All clear!")
    sys.exit(0)


def run():
    parser = argh.ArghParser()
    parser.add_commands([status])
    argh.add_commands(parser, [devstack, rpcs_build],
                      namespace='build', title="build-related commands")
    argh.add_commands(parser, [cloudcafe, ha, tempest],
                      namespace='test',
                      title="test-related commands")

    parser.add_commands([show, update_nodes, upgrade, retrofit, add_nodes,
                         destroy, openrc, horizon, tmux])
    parser.dispatch()


if __name__ == "__main__":
    run()
