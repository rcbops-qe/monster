#! /usr/bin/env python

"""
Command Line interface for Building Openstack clusters
"""
import argh
import subprocess
import traceback
import webbrowser
from monster import util
from monster.config import Config
from monster.tests.ha import HATest
from monster.provisioners.util import get_provisioner
from monster.tests.tempest_neutron import TempestNeutron
from monster.tests.tempest_quantum import TempestQuantum
from monster.deployments.chef_deployment import Chef as MonsterChefDeployment


def build(name="autotest", template="precise-default", branch="master",
          config=None, dry=False, log=None, log_level="INFO",
          provisioner="rackspace", secret_path=None):
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
        try:
            deployment.update_environment()
        except Exception:
            error = traceback.print_exc()
            util.logger.error(error)
            raise

    else:
        util.logger.info(deployment)
        try:
            deployment.build()
        except Exception:
            error = traceback.print_exc()
            util.logger.error(error)
            raise

    util.logger.info(deployment)


def retrofit(name='autotest', retro_branch='dev', ovs_bridge='br-eth1',
             x_bridge='lxb-mgmt', iface='eth0', del_port=None, config=None,
             log=None, log_level='INFO', secret_path=None):

    """
    Retrofit a deployment
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    util.logger.info(deployment)
    deployment.retrofit(retro_branch, ovs_bridge, x_bridge, iface, del_port)


def upgrade(name='autotest', upgrade_branch='v4.1.3rc',
            config=None, log=None, log_level="INFO", secret_path=None):
    """
    Upgrades a current deployment to the new branch / tag
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    util.logger.info(deployment)
    deployment.upgrade(upgrade_branch)


def destroy(name="autotest", config=None, log=None, log_level="INFO",
            secret_path=None):
    """
    Destroys an existing OpenStack deployment
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    util.logger.info(deployment)
    deployment.destroy()


def test(name="autotest", config=None, log=None, log_level="INFO",
         tempest=False, ha=False, secret_path=None, deployment=None,
         iterations=1):
    """
    Tests an openstack deployment
    """
    if not deployment:
        _set_log(log, log_level)
        deployment = _load(name, config, secret_path)
    if not tempest and not ha:
        tempest = True
        ha = True
    if not deployment.feature_in("highavailability"):
        ha = False

    for i in range(iterations):
        print ('\033[1;41mRunning iteration {0} of {1}!'
               '\033[1;m'.format(i + 1, iterations))

        env = deployment.environment.name

        local = "./results/{0}/".format(env)
        #Prepares directory for xml files to be SCPed over
        subprocess.call(['mkdir', '-p', '{0}'.format(local)])

        if ha:
            print ('\033[1;41mRunning High Availability test!'
                   '\033[1;m')
            ha = HATest(deployment)
            ha.test()
        if tempest:
            print ('\033[1;41mRunning Tempest test!'
                   '\033[1;m')
            branch = TempestQuantum.tempest_branch(deployment.branch)
            if "grizzly" in branch:
                tempest = TempestQuantum(deployment)
            else:
                tempest = TempestNeutron(deployment)
            tempest.test()

        controllers = deployment.search_role('controller')
        for controller in controllers:
            ip, user, password = controller.get_creds()
            remote = "{0}@{1}:~/*.xml".format(user, ip)

            getFile(ip, user, password, remote, local)

    print ('\033[1;41mTests have been completed with '
           '{0} iterations!\033[1;m'.format(iterations))


def getFile(ip, user, password, remote, local, remote_delete=False):
    cmd1 = 'sshpass -p {0} scp -q {1} {2}'.format(password, remote, local)
    subprocess.call(cmd1, shell=True)
    if remote_delete:
        cmd2 = ("sshpass -p {0} ssh -o UserKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no -o LogLevel=quiet -l {1} {2}"
                " 'rm *.xml;exit'".format(password, user, ip))
        subprocess.call(cmd2, shell=True)


def artifact(name="autotest", config=None, log=None, secret_path=None,
             log_level="INFO"):
    """
    Artifacts a deployment (configs / running services)
    """

    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    deployment.artifact()


def openrc(name="autotest", config=None, log=None, secret_path=None,
           log_level="INFO"):
    """
    Loads OpenStack credentials into shell env
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    deployment.openrc()


def tmux(name="autotest", config=None, log=None, secret_path=None,
         log_level="INFO"):
    """
    Loads OpenStack nodes into new tmux session
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    deployment.tmux()


def horizon(name="autotest", config=None, log=None, secret_path=None,
            log_level="INFO"):
    """
    Opens horizon in a browser tab
    """
    _set_log(log, log_level)
    deployment = _load(name, config, secret_path)
    ip = deployment.horizon_ip()
    url = "https://{0}".format(ip)
    webbrowser.open_new_tab(url)


def show(name="autotest", config=None, log=None, secret_path=None,
         log_level="INFO"):
    """
    Shows details about and OpenStack deployment
    """
    _set_log(log, log_level)
    # load deployment and source openrc
    deployment = _load(name, config, secret_path)
    util.logger.info(str(deployment))


def _load(name="autotest", config=None, secret_path=None):
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
    parser.add_commands([build, retrofit, upgrade,
                        destroy, openrc, horizon,
                        show, test, tmux])
    parser.dispatch()
