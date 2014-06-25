import monster.features.node.base as node
import monster.active as actv


class Berkshelf(node.Feature):
    """Represents a node with berks installed."""

    def pre_configure(self):
        self._install_berkshelf()

    def apply_feature(self):
        self._write_berks_config()
        self._run_berks()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}

    def _install_berkshelf(self):
        """Installs Berkshelf and correct gems."""

        dependencies = ['libxml2-dev', 'libxslt-dev', 'libz-dev']
        rvm_install = ("curl -L https://get.rvm.io | bash -s -- stable "
                       "--ruby=1.9.3 --autolibs=enable --auto-dotfiles")
        gems = ['berkshelf', 'chef']

        self.node.install_packages(dependencies)
        self.node.run_cmd(rvm_install, attempts=10)
        self.node.install_ruby_gems(gems)

    def _write_berks_config(self):
        """
        Will write the berks config file

        TODO: I need to make this more robust and
        allow you to correctly write the config the way you want.
        For now the ghetto way is how we will do it (jwagner)
        """

        self.node.run_cmd(
            'mkdir -p .berkshelf; cd .berkshelf; echo '
            '"{\\"ssl\\":{\\"verify\\":false}}" > config.json'
        )

    def _run_berks(self):
        """This will run berkshelf to apply the feature """
        self.node.run_cmd(
            "cd /opt/rcbops/swift-private-cloud; source "
            "/usr/local/rvm/scripts/rvm; berks install; berks upload"
        )


class ChefServer(node.Feature):
    """Represents a chef server."""

    def __init__(self, node):
        super(ChefServer, self).__init__(node)

    def pre_configure(self):
        self.node.remove_chef()

    def apply_feature(self):
        self._install()
        self._install_cookbooks()
        self._set_up_remote()
        self.remote_other_nodes()
        self.node.environment.save()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}

    def upgrade(self):
        """Upgrades the Chef Server Cookbooks."""
        self._upgrade_cookbooks()

    def destroy(self):
        pass

    def remote_other_nodes(self):
        for node in self.node.deployment.nodes:
            if not node.has_feature('chefserver') and \
                    not node.has_feature('remote'):
                node.features.insert(0, Remote(node))
                node.save()

    def _install(self):
        """Installs chef server on the given node using a script."""
        url = actv.config['chef']['server']['install_script']
        filename = url.split('/')[-1]
        self.node.run_cmd("curl {url} >> ~/{install_script}; "
                          "chmod u+x ~/{install_script}; ./{install_script}"
                          .format(url=url, install_script=filename))

    def _install_cookbooks(self, directory=None):

        cookbook_url = actv.config['rcbops'][self.node.product]['git']['url']
        cookbook_branch = self.node.branch
        cookbook_name = cookbook_url.split("/")[-1].split(".")[0]
        install_dir = directory or actv.config['chef']['server']['install_dir']

        knife_command = ("mkdir -p {dir}; cd {dir}; git clone {url}; "
                         "cd {cookbook}; git checkout {branch}; "
                         .format(dir=install_dir, url=cookbook_url,
                                 cookbook=cookbook_name,
                                 branch=cookbook_branch))

        if 'cookbooks' in cookbook_name:
            knife_command += ("git submodule init; git submodule sync; git "
                              "submodule update; knife cookbook upload --all "
                              "--cookbook-path {dir}/{cookbook}/cookbooks; "
                              .format(dir=install_dir, cookbook=cookbook_name))

        knife_command += ("knife role from file {dir}/{cookbook}/roles/*.rb"
                          .format(dir=install_dir, cookbook=cookbook_name))

        return self.node.run_cmd(knife_command)

    def _upgrade_cookbooks(self):
        install_dir = actv.config['chef']['server']['upgrade_dir']
        clean = ("for i in /var/chef/cache/cookbooks/*; do rm -rf $i; done; "
                 "rm -rf {dir}".format(dir=install_dir))
        self.node.run_cmd(clean)
        return self._install_cookbooks(directory=install_dir)

    def _set_up_remote(self):
        """Sets up and saves a remote api and dict to the environment."""
        remote_chef = {
            "client": "admin",
            "key": self._get_admin_pem(),
            "url": "https://{0}:443".format(self.node.ipaddress)
        }
        env = self.node.environment
        env.add_override_attr('remote_chef', remote_chef)
        env.chef_server_name = self.node.name
        env.save()

    def _get_admin_pem(self):
        """Gets the admin pem from the chef server."""
        command = "cat ~/.chef/admin.pem"
        pem = self.node.run_cmd(command)["return"]
        if not pem:
            raise Exception("Chef Server setup error")
        return pem


class Cinder(node.Feature):
    """Enables cinder with local lvm backend."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}


class Compute(node.Feature):
    """Represents a RPCS compute """

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        """Archives all services on a compute node."""
        self.save_node_running_services()
        self._set_node_archive()

    def post_configure(self):
        """Run chef-client a second time to lay down host keys."""
        self.node.run()

    def _set_node_archive(self):

        self.archive = {"log": ["nova"], "configs": ["nova"]}


class Controller(node.Feature):
    """Represents a RPCS Controller """

    def __init__(self, node):
        """Initializes node."""
        super(Controller, self).__init__(node)
        self.number = None

    def pre_configure(self):
        """Set controller number and run list based on single or HA features.
        """
        if self.node.deployment.has_controller:
            self.number = 2
            self.set_run_list()
        else:
            self.number = 1
            self.set_run_list()

    def apply_feature(self):
        """Run chef client on controller1 after controller2's completes."""
        self.node.deployment.has_controller = True

        if self.number == 2:
            controller1 = next(self.node.deployment.controllers)
            controller1.run()

    def archive(self):
        """Services on a controller to archive."""

        self.build_archive()
        self.save_node_running_services()
        self._set_node_archive()

    def _set_node_archive(self):
        """Sets a dict in the node object of services and their logs."""

        self.archive = {"log": ["apache2",
                                "apt",
                                "daemon.log",
                                "dist_upgrades",
                                "dmesg",
                                "rsyslog",
                                "syslog",
                                "upstart"],
                        "configs": ["apache2",
                                    "apt",
                                    "collectd",
                                    "dhcp",
                                    "host.conf",
                                    "hostname",
                                    "hosts",
                                    "init",
                                    "init.d",
                                    "network",
                                    "rabbitmq",
                                    "rsyslog.conf",
                                    "rsyslog.d",
                                    "sysctl.conf",
                                    "sysctl.d",
                                    "ufw"]}


class Metrics(node.Feature):
    """Represents a Metrics Node."""

    def __init__(self, node):
        super(Metrics, self).__init__(node)
        self.role = None

    def pre_configure(self):
        if self.node.has_feature('controller'):
            self.role = 'controller'
        else:
            self.role = 'compute'

        self._set_run_list()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}

    def _set_run_list(self):
        """Metrics run list set."""
        role = self.__class__.__name__.lower()
        role_config = actv.config['rcbops'][self.node.product][role][self.role]
        self.node.add_run_list_item(role_config['run_list'])


class Network(node.Feature):
    """Sets the node to be a network."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}


class NetworkManager(node.Feature):

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}


class OpenLDAP(node.Feature):
    """Represents a LDAP server."""

    def pre_configure(self):
        self.set_run_list()

    def post_configure(self):
        self.node.run_cmd('ldapadd -x -D "cn=admin,dc=rcb,dc=me" -wsecrete '
                          '-f /root/base.ldif')

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}


class Orchestration(node.Feature):

    def __init__(self, node):
        super(Orchestration, self).__init__(node)
        self.number = None

    def pre_configure(self):
        if self.node.deployment.has_orch_master:
            self.number = 2
            self.set_run_list()
        else:
            self.number = 1
            self.set_run_list()

    def apply_feature(self):
        self.node.deployment.has_orch_master = True

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}


class Proxy(node.Feature):
    """Represents a RPCS proxy node."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}


class Remote(node.Feature):
    """Represents the deployment having a remote chef server."""

    def pre_configure(self):
        self.node.remove_chef()
        self._bootstrap_chef()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}

    def _bootstrap_chef(self):
        """Bootstraps the node to a chef server."""
        chef_server = self.node.deployment.first_node_with_role('chefserver')
        client_version = actv.config['chef']['client']['version']

        chef_server.run_cmd(
            "knife bootstrap {node} -u root -P {password} --bootstrap-version "
            "{version}".format(node=self.node.ipaddress,
                               password=self.node.password,
                               version=client_version))
        self.node.save()


class Storage(node.Feature):
    """Represents a RPCS proxy node."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""], "configs": [""]}
