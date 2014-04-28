from chef import ChefAPI
from monster import util
from monster.features.base_feature import Feature


class NodeFeature(Feature):
    """Represents a feature on a node."""

    def __init__(self, node):
        """Initialize Node object.
        :type node: monster.nodes.base_node_wrapper.BaseNodeWrapper
        """
        self.node = node

    def __repr__(self):
        return 'class: ' + self.__class__.__name__

    def pre_configure(self):
        pass

    def apply_feature(self):
        pass

    def post_configure(self):
        pass

    def artifact(self):
        pass

    def upgrade(self):
        pass

    def set_run_list(self):
        """Sets the nodes run list based on the feature."""

        # have to add logic for controllers
        if hasattr(self, "number"):
            # Set the role based on the feature name and number of the node
            role = "{0}{1}".format(self.__class__.__name__.lower(),
                                   self.number)
        else:
            role = self.__class__.__name__.lower()

        # Set the run list based on the deployment config for the role
        run_list = util.config['rcbops'][self.node.product][role]['run_list']

        # Add the run list to the node
        self.node.add_run_list_item(run_list)

    def build_archive(self):
        """Builds an archive to save node information."""
        self.log_path = '/tmp/archive/var/log'
        self.etc_path = '/tmp/archive/etc'
        self.misc_path = '/tmp/archive/misc'

        build_archive_cmd = "; ".join("mkdir -p {0}".format(path)
                                      for path in (self.log_path,
                                                   self.etc_path,
                                                   self.misc_path))

        self.node.run_cmd(build_archive_cmd)

    def save_node_running_services(self):
        store_running_services = "{0} > {1}/running-services.out".format(
            self.deployment.list_packages_cmd, self.misc_path)
        self.run_cmd(store_running_services)


class Berkshelf(NodeFeature):
    """Represents a node with berks installed."""

    def pre_configure(self):
        self._install_berkshelf()

    def apply_feature(self):
        self._write_berks_config()
        self._run_berks()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}

    def _install_berkshelf(self):
        """Installs Berkshelf and correct rvms/gems."""

        dependencies = ['libxml2-dev', 'libxslt-dev', 'libz-dev']
        rvm_install = ("curl -L https://get.rvm.io | bash -s -- stable "
                       "--ruby=1.9.3 --autolibs=enable --auto-dotfiles")
        gems = ['berkshelf', 'chef']

        self.node.install_packages(dependencies)
        # We commonly see issues with rvms servers, so loop
        self.node.run_cmd(rvm_install, attempts=10)
        self.node.install_ruby_gems(gems)

    def _write_berks_config(self):
        """
        Will write the berks config file

        TODO: I need to make this more robust and
        allow you to correctly write the config the way you want.
        For now the ghetto way is how we will do it (jwagner)
        """

        command = ('mkdir -p .berkshelf; cd .berkshelf; '
                   'echo "{\\"ssl\\":{\\"verify\\":false}}" > config.json')

        self.node.run_cmd(command)

    def _run_berks(self):
        """This will run berkshelf to apply the feature """
        commands = ['cd /opt/rcbops/swift-private-cloud',
                    'source /usr/local/rvm/scripts/rvm',
                    'berks install',
                    'berks upload']
        self.node.run_cmds(commands)


class ChefServer(NodeFeature):
    """Represents a chef server."""

    def __init__(self, node):
        super(ChefServer, self).__init__(node)
        self.iscript = util.config['chef']['server']['install_script']
        self.iscript_name = self.iscript.split('/')[-1]
        self.script_download = 'curl {0} >> {1}'.format(self.iscript,
                                                        self.iscript_name)
        self.install_commands = ['chmod u+x ~/{0}'.format(self.iscript_name),
                                 './{0}'.format(self.iscript_name)]

    def pre_configure(self):
        self.node.remove_chef()

    def apply_feature(self):
        self._install()
        self._install_cookbooks()
        self._set_up_remote()
        self._remote_other_nodes()
        self.node.environment.save()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}

    def upgrade(self):
        """Upgrades the Chef Server Cookbooks."""
        self._upgrade_cookbooks()

    def destroy(self):
        # Stop updating remote environment
        self.node.environment.remote_api = None

    def _install(self):
        """Installs chef server on the given node."""

        self.node.run_cmd(self.script_download, attempts=5)
        command = "; ".join(self.install_commands)
        self.node.run_cmd(command)

    def _install_cookbooks(self, directory=None):
        """Installs cookbooks """

        cookbook_url = util.config['rcbops'][self.node.product]['git']['url']
        cookbook_branch = self.node.branch
        cookbook_name = cookbook_url.split("/")[-1].split(".")[0]
        install_dir = directory or util.config['chef']['server']['install_dir']

        commands = ["mkdir -p {0}".format(install_dir),
                    "cd {0}".format(install_dir),
                    "git clone {0}".format(cookbook_url),
                    "cd {0}/{1}".format(install_dir, cookbook_name),
                    "git checkout {0}".format(cookbook_branch)]

        if 'cookbooks' in cookbook_name:
             # add submodule stuff to list
            commands.append('git submodule init')
            commands.append('git submodule sync')
            commands.append('git submodule update')
            commands.append('knife cookbook upload --all --cookbook-path '
                            '{0}/{1}/cookbooks'.format(install_dir,
                                                       cookbook_name))

        commands.append('knife role from file {0}/{1}/roles/*.rb'.format(
            install_dir, cookbook_name))

        command = "; ".join(commands)

        return self.node.run_cmd(command)

    def _upgrade_cookbooks(self):
        install_dir = util.config['chef']['server']['upgrade_dir']
        clean = ["for i in /var/chef/cache/cookbooks/*; do rm -rf $i; done",
                 "rm -rf {0}".format(install_dir)]
        self.node.run_cmd("; ".join(clean))
        return self._install_cookbooks(directory=install_dir)

    def _set_up_remote(self):
        """Sets up and saves a remote api and dict to the nodes environment.
        """

        remote_chef = {
            "client": "admin",
            "key": self._get_admin_pem(),
            "url": "https://{0}:443".format(self.node.ipaddress)
        }

        # set the remote chef server name
        self.node.environment.chef_server_name = self.node.name

        # save the remote dict
        self.node.environment.add_override_attr('remote_chef', remote_chef)

        # set the remote api
        remote_api = self._remote_chef_api(remote_chef)
        self.node.environment.remote_api = remote_api

    @classmethod
    def _remote_chef_api(cls, chef_api_dict):
        """Builds a remote chef API object."""

        return ChefAPI(**chef_api_dict)

    def _get_admin_pem(self):
        """Gets the admin pem from the chef server."""

        command = 'cat ~/.chef/admin.pem'
        pem = self.node.run_cmd(command)['return']
        if not pem:
            raise Exception("Chef Server setup error")
        return pem

    def _remote_other_nodes(self):
        for node in self.node.deployment.nodes:
            if not node.has_feature("chefserver"):
                remote_feature = Remote(node)
                node.features.insert(0, remote_feature)
                node.save_to_node()


class Cinder(NodeFeature):
    """Enables cinder with local lvm backend."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}


class Compute(NodeFeature):
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

        self.archive = {"log": ["nova"],
                        "configs": ["nova"]}


class Controller(NodeFeature):
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
            controllers = self.node.deployment.search_role('controller')
            controller1 = next(controllers)
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
                                    "rsylog.conf",
                                    "rsyslog.d",
                                    "sysctl.conf",
                                    "sysctl.d",
                                    "ufw"]}


class Metrics(NodeFeature):
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
        self.archive = {"log": [""],
                        "configs": [""]}

    def _set_run_list(self):
        """Metrics run list set."""

        role = self.__class__.__name__.lower()

        # Set the run list based on the deployment config for the role
        run_list = util.config['rcbops'][self.node.product][
            role][self.role]['run_list']

        # Add the run list to the node
        self.node.add_run_list_item(run_list)


class Network(NodeFeature):
    """Sets the node to be a network."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}


class NetworkManager(NodeFeature):

    def preconfigure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}


class OpenLDAP(NodeFeature):
    """Represents a LDAP server."""

    def pre_configure(self):
        self.set_run_list()

    def post_configure(self):
        self._configure_ldap()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}

    def _configure_ldap(self):
        ldapadd = ('ldapadd -x -D "cn=admin,dc=rcb,dc=me" '
                   '-wsecrete -f /root/base.ldif')
        self.node.run_cmd(ldapadd)


class Orchestration(NodeFeature):

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
        self.archive = {"log": [""],
                        "configs": [""]}


class Proxy(NodeFeature):
    """Represents a RPCS proxy node."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}


class Remote(NodeFeature):
    """Represents the deployment having a remote chef server."""

    def pre_configure(self):
        self.node.remove_chef()
        self._bootstrap_chef()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}

    def _bootstrap_chef(self):
        """Bootstraps the node to a chef server. """

        # Gather the info for the chef server
        chef_server = next(self.node.deployment.search_role('chefserver'))
        client_version = util.config['chef']['client']['version']

        command = ("knife bootstrap {0} -u root -P {1}"
                   " --bootstrap-version {2}".format(self.node.ipaddress,
                                                     self.node.password,
                                                     client_version))

        chef_server.run_cmd(command)
        self.node.save()


class Storage(NodeFeature):
    """Represents a RPCS proxy node."""

    def pre_configure(self):
        self.set_run_list()

    def archive(self):
        self.archive = {"log": [""],
                        "configs": [""]}
