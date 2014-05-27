#! /usr/bin/env python
"""
Command-line interface for building OpenStack clusters
"""

import os
import subprocess
import argh

import monster.db_iface as database
from monster.data import data
from monster.logger import logger as monster_logger
from monster.utils.access import get_file
from monster.utils.color import Color
from monster.orchestrator.util import get_orchestrator
from monster.tests.ha import HATest
from monster.tests.cloudcafe import CloudCafe
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum


logger = monster_logger.Logger().logger_setup()


@database.store_build_params
def rpcs(name, template="ubuntu-default", branch="master",
         config="pubcloud-neutron.yaml", dry=False,
         log=None, provisioner="rackspace",
         secret="secret.yaml", orchestrator="chef"):
    """Build an Rackspace Private Cloud deployment."""
    data.load_config(name)

    orchestrator = get_orchestrator(orchestrator)
    deployment = orchestrator.create_deployment_from_file(name)

    if dry:
        deployment.update_environment()
    else:
        deployment.build()

    database.store(deployment)
    logger.info(deployment)


@database.store_build_params
def devstack(name, template="ubuntu-default", branch="master",
             config="pubcloud-neutron.yaml", dry=False,
             log=None, provisioner="rackspace",
             secret="secret.yaml", orchestrator="chef"):
    """Build an devstack deployment."""
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
    controllers = deployment.search_role('controller')
    for controller in controllers:
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
    controllers = deployment.search_role('controller')
    for controller in controllers:
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


def _load(name, orchestrator_name="chef"):
    orchestrator = get_orchestrator(orchestrator_name)
    deployment = orchestrator.load_deployment_from_name(name)
    return deployment


def status():
    pass
# check to ensure the DB is up and running on port 6379
# check to ensure the secret credentials exist and are valid


def run():
    parser = argh.ArghParser()
    parser.add_commands([retrofit, upgrade, destroy,
                         openrc, horizon, show, tmux])

    argh.add_commands(parser, [devstack, rpcs], namespace='build',
                      title="build-related commands")
    argh.add_commands(parser, [cloudcafe, ha, tempest],
                      namespace='test',
                      title="test-related commands")

    if 'monster' not in os.environ.get('VIRTUAL_ENV', ''):
        logger.warning("You are not using the virtual environment! We "
                       "cannot guarantee that your monster will be well"
                       "-behaved.  To load the virtual environment, use "
                       "the command \"source .venv/bin/activate\"")
    parser.dispatch()


if __name__ == "__main__":
    run()
