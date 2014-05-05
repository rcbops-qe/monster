#! /usr/bin/env python
"""
Command-line interface for building OpenStack clusters
"""

import os
import subprocess
import traceback

import argh

import monster.config

from monster import util
from monster.tools.color import Color
from monster.orchestrator.util import get_orchestrator
from monster.tests.ha import HATest
from monster.tests.cloudcafe import CloudCafe
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum

logger = util.Logger().logger_setup()


def rpcs(name, template="ubuntu-default", branch="master",
         template_path=None, config="pubcloud-neutron.yaml",
         dry=False, log=None, provisioner_name="rackspace",
         secret_path=None, orchestrator_name="chef"):
    """Build an Rackspace Private Cloud deployment."""
    _load_config(config, secret_path)

    orchestrator = get_orchestrator(orchestrator_name)
    deployment = orchestrator.create_deployment_from_file(name, template,
                                                          branch,
                                                          provisioner_name)
    try:
        if dry:
            deployment.update_environment()
        else:
            deployment.build()
    except Exception:
        error = traceback.print_exc()
        logger.exception(error)

    logger.info(deployment)


def devstack(name, template="ubuntu-default", branch="master",
             template_path=None, config="pubcloud-neutron.yaml",
             dry=False, log=None, provisioner_name="rackspace",
             secret_path=None, orchestrator_name="chef"):
    """Build an devstack deployment."""
    _load_config(config, secret_path)

    orchestrator = get_orchestrator(orchestrator_name)
    deployment = orchestrator.create_deployment_from_file(name, template,
                                                          branch,
                                                          provisioner_name)
    try:
        if dry:
            deployment.update_environment()
        else:
            deployment.build()
    except Exception:
        error = traceback.print_exc()
        logger.exception(error)

    logger.info(deployment)


def tempest(name, config="pubcloud-neutron.yaml", log=None,
            secret_path=None, deployment=None, iterations=1, progress=False):
    """Test an OpenStack deployment."""
    if not deployment:
        deployment = _load(name, config, secret_path)

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
        util.get_file(ip, user, password, remote, local)

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


def ha(name, config="pubcloud-neutron.yaml", log=None,
       secret_path=None, deployment=None, iterations=1, progress=False):
    """Test an OpenStack deployment."""
    if not deployment:
        deployment = _load(name, config, secret_path)
    # if deployment.has_feature("highavailability"):

    test_object = HATest(deployment, progress)

    env = deployment.environment.name
    local = "./results/{0}/".format(env)
    controllers = deployment.search_role('controller')
    for controller in controllers:
        ip, user, password = controller.creds
        remote = "{0}@{1}:~/*.xml".format(user, ip)
        util.get_file(ip, user, password, remote, local)

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
             x_bridge='lxb-mgmt', iface='eth0', del_port=None, config=None,
             log=None, secret_path=None):
    """Retrofit a deployment."""
    deployment = _load(name, config, secret_path)
    logger.info(deployment)
    deployment.retrofit(retro_branch, ovs_bridge, x_bridge, iface, del_port)


def upgrade(name='autotest', upgrade_branch='v4.1.3rc',
            config=None, log=None, secret_path=None):
    """Upgrade a current deployment to the new branch / tag."""
    deployment = _load(name, config, secret_path)
    logger.info(deployment)
    deployment.upgrade(upgrade_branch)


def destroy(name, config="pubcloud-neutron.yaml",
            log=None, secret_path=None):
    """Destroy an existing OpenStack deployment."""
    deployment = _load(name, config, secret_path=secret_path)
    logger.info(deployment)
    deployment.destroy()


def artifact(name, config=None, log=None, secret_path=None):
    """Artifact a deployment (configs/running services)."""
    deployment = _load(name, config, secret_path)
    deployment.artifact()


def openrc(name, config=None, log=None, secret_path=None):
    """Export OpenStack credentials into shell environment."""
    deployment = _load(name, config, secret_path)
    deployment.openrc()


def tmux(name, config=None, log=None, secret_path=None):
    """Load OpenStack nodes into a new tmux session."""
    deployment = _load(name, config, secret_path)
    deployment.tmux()


def horizon(name, config=None, log=None, secret_path=None):
    """Open Horizon in a browser tab."""
    deployment = _load(name, config, secret_path)
    deployment.horizon()


def show(name, config=None, log=None, secret_path=None):
    """Show details about an OpenStack deployment."""
    deployment = _load(name, config, secret_path)
    logger.info(str(deployment))


def cloudcafe(cmd, name, network=None, config=None,
              secret_path=None):
    deployment = _load(name, config, secret_path)
    CloudCafe(deployment).config(cmd, network_name=network)


def _load_config(config, secret_path):
    if "configs/" not in config:
        config = "configs/{}".format(config)
    util.config = monster.config.fetch_config(config, secret_path)


def _load(name, config="config.yaml", secret_path=None,
          orchestrator_name="chef"):
    # Load deployment and source openrc
    _load_config(config, secret_path)
    orchestrator = get_orchestrator(orchestrator_name)
    deployment = orchestrator.load_deployment_from_name(name)
    return deployment


def run():
    parser = argh.ArghParser()
    parser.add_commands([retrofit, upgrade, destroy, openrc, horizon, show,
                         tmux])

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
