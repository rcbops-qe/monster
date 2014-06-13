import monster.active as active


class Upgrade(object):
    """Base upgrade class."""

    def __init__(self, deployment):
        self.deployment = deployment

        if self.deployment.os_name == "ubuntu":
            self.pkg_up_cmd = "apt-get"

        if self.deployment.os_name == "centos":
            self.pkg_up_cmd = "yum"

    def upgrade(self, rc=False):
        raise NotImplementedError

    def deployment_nodes(self):
        """Returns a deployment's nodes."""

        return (self.deployment.first_node_with_role('chefserver'),
                list(self.deployment.controllers),
                list(self.deployment.computes))

    def fix_celiometer(self):
        """Fixes a deployment's Celiometer."""
        cmd = ("{0} clean; {0} update; {0} -y install python-warlock "
               "python-swiftclient babel".format(self.pkg_up_cmd))

        for controller in self.deployment.controllers:
            controller.run_cmd(cmd)

        for compute in self.deployment.computes:
            compute.run_cmd(cmd)

    def fix_horizon(self):
        """Fixes a deployment's Horizon."""
        cmd = ("{0} clean; {0} update; {0} -y install openstack-dashboard "
               "python-django-horizon".format(self.pkg_up_cmd))

        for controller in self.deployment.controllers:
            controller.run_cmd(cmd)

    def fix_qemu(self):
        """Fixes a deployment's QEMU."""
        node_commands = ("{0} update; {0} remove qemu-utils -y; "
                         "{0} install qemu-utils -y".format(self.pkg_up_cmd))

        for controller in self.deployment.controllers:
            controller.run_cmd(node_commands)

        for compute in self.deployment.computes:
            compute.run_cmd(node_commands)

    def mungerate(self):
        """Runs RCBOPS mungerator for upgrading 4.1.x to 4.2.x or from Grizzly
        to Havana.
        """

        chef_server = self.deployment.chef_server()
        munge = []

        # For mungerator
        if self.deployment.os_name == "ubuntu":
            munge.extend(["{0} -y install python-dev python-setuptools"
                          .format(self.pkg_up_cmd)])
        if self.deployment.os_name == "centos":
            munge.extend(["{0} install -y openssl-devel python-devel "
                          "python-setuptools".format(self.pkg_up_cmd)])

        backup = active.config['upgrade']['commands']['backup-db']
        self.deployment.controller(1).run_cmd(backup)

        munge_dir = "/opt/upgrade/mungerator"
        munge_repo = "https://github.com/rcbops/mungerator"
        munge.extend([
            "rm -rf {0}".format(munge_dir),
            "git clone {0} {1}".format(munge_repo, munge_dir),
            "cd {0}; python setup.py install".format(munge_dir),
            "mungerator munger --client-key /etc/chef-server/admin.pem "
            "--auth-url https://127.0.0.1:443 all-nodes-in-env "
            "--name {0}".format(self.deployment.name)])
        chef_server.run_cmd("; ".join(munge))
        self.deployment.environment.save_remote_to_local()

    def pre_upgrade(self):
        """Does upgrade prep."""
        self.fix_celiometer()

    def post_upgrade(self):
        """Fix stuff post-upgrade."""
        self.fix_horizon()

        provisioner = str(self.deployment.provisioner)
        if provisioner == "rackspace" or provisioner == "openstack":
            self.fix_qemu()
