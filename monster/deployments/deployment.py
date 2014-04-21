"""
OpenStack deployments
"""
import logging
import types
import tmuxp

from pyrabbit.api import Client

from monster.tools.retrofit import Retrofit

logger = logging.getLogger(__name__)


class Deployment(object):
    """Base for OpenStack deployments
    """

    def __init__(self, name, os_name, branch, provisioner, status, product,
                 clients=None):
        self.name = name
        self.os_name = os_name
        self.branch = branch
        self.features = []
        self.nodes = []
        self.status = status or "Provisioning..."  # i don't like this default
        self.provisioner = str(provisioner)
        self.product = product
        self.clients = clients

    def __repr__(self):
        """
        Print out current instance
        """

        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            if attr == 'features':
                features = "\tFeatures: {0}".format(
                    ", ".join((str(f) for f in self.features)))
            elif attr == 'nodes':
                nodes = "\tNodes: {0}".format(
                    "".join((str(n) for n in self.nodes)))
            elif isinstance(getattr(self, attr), types.NoneType):
                outl += '\n\t{0} : {1}'.format(attr, 'None')
            else:
                outl += '\n\t{0} : {1}'.format(attr, getattr(self, attr))

        return "\n".join([outl, features, nodes])

    def destroy(self):
        """
        Destroys an OpenStack deployment
        """

        self.status = "Destroying..."
        logger.info("Destroying deployment: {0}".format(self.name))
        for node in self.nodes:
            node.destroy()
        self.status = "Destroyed!"

    def update_environment(self):
        """
        Preconfigures node for each feature
        """

        logger.info("Building Configured Environment")
        self.status = "Loading environment..."
        for feature in self.features:
            logger.debug("Deployment feature {0}: updating environment".format(
                str(feature))
            )
            feature.update_environment()
        logger.debug(self.environment)
        self.status = "Environment ready!"

    def pre_configure(self):
        """
        Preconfigures node for each feature
        """

        self.status = "Pre-configuring nodes for features..."
        for feature in self.features:
            logger.debug("Deployment feature: pre-configure: {0}".format(
                str(feature))
            )
            feature.pre_configure()

    def build_nodes(self):
        """
        Builds each node
        """

        self.status = "Building nodes..."
        for node in self.nodes:
            logger.debug("Building node {0}!".format(str(node)))
            node.build()
        self.status = "Nodes built!"

    def post_configure(self):
        """
        Post configures node for each feature
        """

        self.status = "Post-configuration..."
        for feature in self.features:
            log = "Deployment feature: post-configure: {0}"\
                .format(str(feature))
            logger.debug(log)
            feature.post_configure()

    def build(self):
        """
        Runs build steps for node's features
        """

        logger.debug("Deployment step: update environment")
        self.update_environment()
        logger.debug("Deployment step: pre-configure")
        self.pre_configure()
        logger.debug("Deployment step: build nodes")
        self.build_nodes()
        logger.debug("Deployment step: post-configure")
        self.post_configure()
        self.status = "post-build"
        logger.info(self)

    def artifact(self):
        """
        Artifacts openstack and its dependant services for a deployment
        """

        self.log_path = "/var/log"
        self.etc_path = "/etc/"
        self.misc_path = "misc/"

        if self.deployment.os_name == 'ubuntu':
            self.list_packages_cmd = ["dpkg -l"]
        else:
            self.list_packages_cmd = ["rpm -qa"]

        # Run each features archive
        for feature in self.features:
            feature.archive()

        # Run each nodes archive
        for node in self.nodes:
            node.archive()

    def search_role(self, feature):
        """
        Returns nodes the have the desired role
        :param feature: feature to be searched for
        :type feature: string
        :rtype: Iterator (Nodes)
        """

        return (node for node in
                self.nodes if feature in
                (str(f).lower() for f in node.features))

    def feature_in(self, feature):
        """
        Boolean function to determine if a feature exists in deployment
        :param feature: feature to be searched for
        :type feature: string
        :rtype: Boolean
        """

        if feature in (feature.__class__.__name__.lower()
                       for feature in self.features):
            return True
        return False

    def tmux(self):
        """
        Creates an new tmux session with an window for each node
        """

        server = tmuxp.Server()
        session = server.new_session(session_name=self.name)
        cmd = ("sshpass -p {1} ssh -o UserKnownHostsFile=/dev/null "
               "-o StrictHostKeyChecking=no -o LogLevel=quiet "
               "-o ServerAliveInterval=5 -o ServerAliveCountMax=1 -l root {0}")
        for node in self.nodes:
            name = node.name[len(self.name) + 1:]
            window = session.new_window(window_name=name)
            pane = window.panes[0]
            pane.send_keys(cmd.format(node.ipaddress, node.password))

    @property
    def feature_names(self):
        """
        Returns list features as strings
        :rtype: list (string)
        """

        return [feature.__class__.__name__.lower() for feature in
                self.features]

    def retrofit(self, branch, ovs_bridge, lx_bridge, iface, del_port=None):
        """
        Retrofit the deployment
        """

        logger.info("Retrofit Deployment: {0}".format(self.name))

        retrofit = Retrofit(self)

        # if old port exists, remove it
        if del_port:
            retrofit.remove_port_from_bridge(ovs_bridge, del_port)

        # Install
        retrofit.install(branch)

        # Bootstrap
        retrofit.bootstrap(iface, lx_bridge, ovs_bridge)

    @property
    def rabbitmq_mgmt_client(self):
        """
        Return rabbitmq mgmt client
        """
        overrides = self.environment.override_attributes
        if 'vips' in overrides:
            # HA
            ip = overrides['vips']['rabbitmq-queue']
        else:
            # Non HA
            controller = next(self.search_role("controller"))
            ip = controller.ipaddress
        url = "{ip}:15672".format(ip=ip)

        user = "guest"
        password = "guest"

        client = Client(url, user, password)
        return client
