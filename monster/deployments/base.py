import types
import logging

import tmuxp

import monster.features.deployment.features as deployment_features
import monster.active as active
import monster.threading_iface as threading
import monster.db_iface as database
from monster.orchestrator.util import get_orchestrator
from monster.utils.retrofit import Retrofit
from monster.utils.introspection import module_classes
from monster.provisioners.util import get_provisioner


logger = logging.getLogger(__name__)


class Deployment(object):
    """Base for OpenStack deployments."""
    def __init__(self, name, status=None, clients=None):
        self.name = name
        self.os_name = active.template['os']
        self.branch = active.build_args['branch']
        self.orchestrator = get_orchestrator(active.build_args['orchestrator'])
        self.environment = self.orchestrator.get_env(name)
        self.nodes = []
        self.features = []
        self.status = status or "provisioning"
        self.provisioner_name = active.build_args['provisioner']
        self.product = active.template['product']
        self.clients = clients
        self.add_features(active.template['features'])

    def __repr__(self):
        features = "\tFeatures: %s" % self.feature_names
        nodes = "\tNodes: %s" % self.node_names

        output = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            if isinstance(getattr(self, attr), types.NoneType):
                output += '\n\t{0} : {1}'.format(attr, 'None')
            else:
                output += '\n\t{0} : {1}'.format(attr, getattr(self, attr))

        return "\n".join([output, features, nodes])

    def build(self):
        """Runs build steps for node's features."""
        logger.info("Building deployment object for {}".format(self.name))
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
        database.store(self)

    def update(self):
        """Updates a deployment's nodes, both via package managers and any
        orchestration system in play, such as by running chef-client."""
        for node in self.nodes:
            node.update_packages()

    def update_environment(self):
        """Preconfigures node for each feature."""
        logger.info("Updating environment with deployment features...")
        self.status = "Loading environment..."
        for feature in self.features:
            logger.debug("Deployment feature {feature}: updating environment!"
                         .format(feature=feature))
            feature.update_environment()
        self.status = "Environment ready!"

    def pre_configure(self):
        """Preconfigures node for each feature."""
        self.status = "Pre-configuring nodes for features..."
        for feature in self.features:
            logger.debug("Deployment feature: pre-configure: {feature}"
                         .format(feature=feature))
            feature.pre_configure()

    def build_nodes(self):
        """Builds each node."""
        logger.info("Building controllers...")
        for node in self.controllers:
            node.build()
        logger.info("Building the rest of the nodes.")
        threading.execute(node.build for node in self.misc_nodes)
        self.status = "Nodes built!"

    def post_configure(self):
        """Post configures node for each feature."""
        self.status = "post-configuration..."
        for feature in self.features:
            logger.debug("Deployment feature: post-configure: {}"
                         .format(feature))
            feature.post_configure()

    def destroy(self):
        """Destroys an OpenStack deployment."""
        self.status = "destroying..."
        logger.info("Destroying deployment: {}".format(self.name))
        for node in self.nodes:
            self.provisioner.destroy_node(node)
        database.remove_key(self.name)
        self.status = "Destroyed!"

    def artifact(self):
        """Artifacts OpenStack and its dependent services for a deployment."""
        for feature in self.features:
            feature.archive()

        for node in self.nodes:
            node.archive()

    def nodes_with_role(self, feature_name):
        """Returns nodes that have a specified role."""
        return (node for node in self.nodes
                if node.has_feature(feature_name))

    def nodes_without_role(self, feature_name):
        """Returns nodes that do not have a specified role."""
        return (node for node in self.nodes
                if not node.has_feature(feature_name))

    def first_node_with_role(self, feature_name):
        return next(self.nodes_with_role(feature_name))

    def has_feature(self, feature_name):
        """Boolean function to determine if a feature exists in deployment."""
        return feature_name in self.feature_names

    def add_features(self, features):
        """Adds a dictionary of features to deployment.
        :param features: dictionary of features {"monitoring": "default", ...}
        :type features: dict
        """
        # stringify and lowercase classes in deployment features
        classes = module_classes(deployment_features)
        for feature, rpcs_feature in features.items():
            logger.debug("feature: {0}, "
                         "rpcs_feature: {1}".format(feature, rpcs_feature))
            self.features.append(classes[feature](self, rpcs_feature))

    def tmux(self):
        """Creates an new tmux session with an window for each node."""
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
        """Returns list of features as strings.
        :rtype: list (str)
        """
        return [str(feature).lower() for feature in self.features]

    @property
    def node_names(self):
        """Returns list of nodes as strings.
        :rtype: list (str)
        """
        return [node.name for node in self.nodes]

    @property
    def override_attrs(self):
        """Override attributes for the deployment, which are stored in the
        deployment's environment.
        """
        return self.environment.override_attributes

    @property
    def provisioner(self):
        return get_provisioner(self.provisioner_name)

    @property
    def controllers(self):
        return self.nodes_with_role('controller')

    def controller(self, controller_num):
        """Returns the requested controller, if the node has it."""
        try:
            return next(node for node in self.controllers
                        if node.feature('controller').number == controller_num)
        except StopIteration:
            logger.warning("{} does not have a controller number {}"
                           .format(self.name, controller_num))

    @property
    def computes(self):
        return self.nodes_with_role('compute')

    @property
    def misc_nodes(self):
        return [node for node in self.nodes
                if not node.has_feature('chefserver')
                and not node.has_feature('controller')]

    def retrofit(self, branch, ovs_bridge, lx_bridge, iface,
                 old_port_to_delete=None):
        """Retrofit the deployment."""

        logger.info("Retrofit Deployment: {0}".format(self.name))

        retrofit = Retrofit(self)

        if old_port_to_delete:
            retrofit.remove_port_from_bridge(ovs_bridge, old_port_to_delete)

        retrofit.install(branch)
        retrofit.bootstrap(iface, lx_bridge, ovs_bridge)

    def upgrade(self, upgrade_branch):
        pass

    def openrc(self):
        pass

    def horizon(self):
        pass

    def add_nodes(self, node_request):
        pass
