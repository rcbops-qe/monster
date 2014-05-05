import monster.active as active


class Upgrade(object):
    """
    Base upgrade class
    """

    def __init__(self, deployment):
        self.deployment = deployment

        if self.deployment.os_name == "ubuntu":
            self.pkg_up_cmd = "apt-get"

        if self.deployment.os_name == "centos":
            self.pkg_up_cmd = "yum"

    def upgrade(self, rc=False):
        raise NotImplementedError

    def deployment_nodes(self):
        """
        Returns a deployments nodes
        """

        return (self.deployment_chef_server(),
                self.deployment_controllers(),
                self.deployment_computes())

    def deployment_chef_server(self):
        """
        Returns the deployments chef server
        """

        return next(self.deployment.search_role('chefserver'))

    def deployment_controllers(self):
        """
        Returns a deployments controller(s)
        """

        return list(self.deployment.search_role('controller'))

    def deployment_computes(self):
        """
        Returns a deployments computes
        """

        return list(self.deployment.search_role('compute'))

    def fix_celiometer(self):
        """
        Fixes a deployments fix_celiometer
        """
        controllers = self.deployment_controllers()
        computes = self.deployment_computes()
        ncmds = ["{0} clean".format(self.pkg_up_cmd),
                 "{0} update".format(self.pkg_up_cmd),
                 "{0} -y install python-warlock".format(self.pkg_up_cmd),
                 "{0} -y install python-swiftclient".format(self.pkg_up_cmd),
                 "{0} -y install babel".format(self.pkg_up_cmd)]

        node_commands = "; ".join(ncmds)

        for controller in controllers:
            controller.run_cmd(node_commands)

        for compute in computes:
            compute.run_cmd(node_commands)

    def fix_horizon(self):
        """
        Fixes a deployments horizon
        """
        controllers = self.deployment_controllers()
        ccmds = [
            "{0} clean".format(self.pkg_up_cmd),
            "{0} update".format(self.pkg_up_cmd),
            "{0} -y install openstack-dashboard".format(self.pkg_up_cmd),
            "{0} -y install python-django-horizon".format(self.pkg_up_cmd)
        ]
        controller_commands = "; ".join(ccmds)

        for controller in controllers:
            controller.run_cmd(controller_commands)

    def fix_qemu(self):
        """
        Fixes a deployments QEMU
        """
        controllers = self.deployment_controllers()
        computes = self.deployment_computes()
        ncmds = (["{0} update".format(self.pkg_up_cmd),
                  "{0} remove qemu-utils -y".format(self.pkg_up_cmd),
                  "{0} install qemu-utils -y".format(self.pkg_up_cmd)])
        node_commands = "; ".join(ncmds)

        for controller in controllers:
            controller.run_cmd(node_commands)

        for compute in computes:
            compute.run_cmd(node_commands)

    def mungerate(self):
        """
        Runs RCBOPS mungerator for upgradinf 4.1.x to 4.2.x
        or from grizzly to havana
        """

        chef_server = self.deployment_chef_server()
        controllers = self.deployment_controllers()
        controller1 = controllers[0]
        munge = []

        # For mungerator
        if self.deployment.os_name == "ubuntu":
            munge.extend([
                "{0} -y install python-dev".format(self.pkg_up_cmd),
                "{0} -y install python-setuptools".format(self.pkg_up_cmd)
            ])
        if self.deployment.os_name == "centos":
            munge.extend([
                "{0} install -y openssl-devel".format(self.pkg_up_cmd),
                "{0} install -y python-devel".format(self.pkg_up_cmd),
                "{0} install -y python-setuptools".format(self.pkg_up_cmd)
            ])

        # backup db
        backup = active.config['upgrade']['commands']['backup-db']
        controller1.run_cmd(backup)

        # Mungerate all the things
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
        """
        Does upgrade prep
        """
        self.fix_celiometer()

    def post_upgrade(self):
        """
        Fix stuff post upgrade
        """
        self.fix_horizon()

        # For QEMU
        provisioner = str(self.deployment.provisioner)
        if provisioner == "rackspace" or provisioner == "openstack":
            self.fix_qemu()
