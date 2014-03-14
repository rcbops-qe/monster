#! /usr/bin/env python

"""
Command Line interface for Building Openstack clusters
"""

from monster import util
from IPython import embed
try:
    import subprocess
    import traceback
    import webbrowser
    import os
    import inspect
    from compute_cli import CLI
    from monster.config import Config
    from monster.tests.ha import HATest
    from monster.provisioners.util import get_provisioner
    from monster.tests.tempest_neutron import TempestNeutron
    from monster.tests.tempest_quantum import TempestQuantum
    from monster.deployments.chef_deployment import Chef as ChefDeployment
except ImportError as error:
    util.logger.error("There was an import error when trying to load '{0}' "
                      "This may be resolved if you load the monster virtual"
                      " environment with the command \"source .venv/bin/"
                      "activate\"".format(error.message[16:]))
    exit(1)
if 'monster' not in os.environ.get('VIRTUAL_ENV', ''):
    util.logger.warning("You are not using the virtual environment! We "
                        "cannot guarantee that your monster will be well"
                        "-behaved.  To load the virtual environment, use "
                        "the command \"source .venv/bin/activate\"")

def __log(function):
    def wrap_function(args):
        util.logger.setLevel(args.log_level)
        util.log_to_file(args.logfile_path)
        return function(args)
    return wrap_function

def __load_deployment(function):
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        deployment = ChefDeployment.from_chef_environment(args.name)
        util.logger.debug("Loading deployment {0}".format(deployment))
        return function(deployment, args)
    return wrap_function

def __build_deployment(function):
    def wrap_function(args):
        util.logger.info("Building deployment object for %s" % args.name)
        util.logger.debug("Creating ChefDeployment with dict %s" % args)
        try:
            args.deployment = ChefDeployment.fromfile(**vars(args))
        except TypeError as error:
            util.logger.critical(
                str(error) +
                "ChefDeployment.fromfile was called with \n{0},\n but "
                "expects at least the following non-none : {1}."
                .format(vars(args),
                        inspect.getargspec(ChefDeployment.fromfile)[0][1:]))
            exit(1)
        return function(args)
    return wrap_function

def __provision_for_deployment(function):
    def wrap_function(args):
        util.config = Config(args.config, args.secret_path)
        args.provisioner=get_provisioner(args.provisioner)
        return function(args)
    return wrap_function


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
    Tests an openstack deployment
    """
    if not args.tempest and not args.ha:
        tempest = True
        ha = True
    if not deployment.feature_in("highavailability"):
        ha = False
    if ha:
        ha = HATest(deployment)
    if tempest:
        branch = TempestQuantum.tempest_branch(deployment.branch)
        if "grizzly" in branch:
            tempest = TempestQuantum(deployment)
        else:
            tempest = TempestNeutron(deployment)

    env = deployment.environment.name
    local = "./results/{0}/".format(env)
    controllers = deployment.search_role('controller')
    for controller in controllers:
        ip, user, password = controller.get_creds()
        remote = "{0}@{1}:~/*.xml".format(user, ip)
        getFile(ip, user, password, remote, local)

    for i in range(args.iterations):
        #print ('\033[1;36mRunning iteration {0} of {1}!'
        #       '\033[1;m'.format(i + 1, iterations))

        #Prepares directory for xml files to be SCPed over
        subprocess.call(['mkdir', '-p', '{0}'.format(local)])

        if ha:
            #print ('\033[1;36mRunning High Availability test!'
            #       '\033[1;m')
            ha.test(args.iterations, args.provider_net)
        if tempest:
            #print ('\033[1;36mRunning Tempest test!'
            #       '\033[1;m')
            tempest.test()

    print ('\033[1;36mTests have been completed with '
           '{0} iterations!\033[1;m'.format(args.iterations))


def getFile(ip, user, password, remote, local, remote_delete=False):
    cmd1 = 'sshpass -p {0} scp -q {1} {2}'.format(password, remote, local)
    subprocess.call(cmd1, shell=True)
    if remote_delete:
        cmd2 = ("sshpass -p {0} ssh -o UserKnownHostsFile=/dev/null "
                "-o StrictHostKeyChecking=no -o LogLevel=quiet -l {1} {2}"
                " 'rm *.xml;exit'".format(password, user, ip))
        subprocess.call(cmd2, shell=True)


@__log
@__load_deployment
def retrofit(deployment, retro_branch='dev', ovs_bridge='br-eth1',
             x_bridge='lxb-mgmt', iface='eth0', del_port=None):
    """
    Retrofit a deployment
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
    Opens horizon in a browser tab
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
