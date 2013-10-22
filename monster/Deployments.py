"""
OpenStack deployments
"""

import os
import types
from monster import util
from time import sleep
from chef import autoconfigure, Search, Environment, Node
from inspect import getmembers, isclass

from monster.Config import Config
from monster.razor_api import razor_api
from monster.Environments import Chef
from monster.Nodes import ChefRazorNode
import monster.Features.Deployment as deployment_features


class Deployment(object):
    """Base for OpenStack deployments
    """
    
    def __init__(self, name, os_name, branch, config, status="provisioning"):
        self.name = name
        self.os_name = os_name
        self.branch = branch
        self.config = config
        self.features = []
        self.nodes = []
        self.status = status

    def __repr__(self):
        """ Print out current instance
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
        """ Destroys an OpenStack deployment """
        self.status = "destroying"
        util.logger.info("Destroying deployment:{0}".format(self.name))
        for node in self.nodes:
            node.destroy()
        self.status = "destroyed"

    def update_environment(self):
        """Pre configures node for each feature"""
        self.status = "loading environment"
        for feature in self.features:
            log = "Deployment feature: update environment: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.update_environment()
        util.logger.debug(self.environment)
        self.status = "environment ready"

    def pre_configure(self):
        """Pre configures node for each feature"""
        self.status = "pre-configure"
        for feature in self.features:
            log = "Deployment feature: pre-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.pre_configure()

    def build_nodes(self):
        self.status = "building nodes"
        """Builds each node"""
        for node in self.nodes:
            node.build()
        self.status = "nodes built"

    def post_configure(self):
        """Post configures node for each feature"""
        self.status = "post-configure"
        for feature in self.features:
            log = "Deployment feature: post-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features"""
        util.logger.debug("Deployment step: update environment")
        self.update_environment()
        util.logger.debug("Deployment step: pre-configure")
        self.pre_configure()
        util.logger.debug("Deployment step: build nodes")
        self.build_nodes()
        util.logger.debug("Deployment step: post-configure")
        self.post_configure()
        self.status = "done"

    def test(self):
        """
        Run tests on deployment
        """
        pass


class ChefRazorDeployment(Deployment):
    """ Deployment mechinisms specific to deployment using:
    Puppet's Razor as provisioner and
    Opscode's Chef as configuration management
    """

    def __init__(self, name, os_name, branch, config, environment, razor,
                 status="provisioning"):
        super(ChefRazorDeployment, self).__init__(name, os_name, branch,
                                                  config, status=status)
        self.environment = environment
        self.razor = razor
        self.has_controller = False

    def save_to_environment(self):
        """
        Save deployment restore attributes to chef environment
        """
        features = {key: value for (key, value) in
                    ((str(x).lower(), x.rpcs_feature) for x in self.features)}
        nodes = [n.name for n in self.nodes]
        deployment = {'nodes': nodes,
                      'os_features': features,
                      'rpcs_features': {},
                      'name': self.name,
                      'os_name': self.os_name,
                      'branch': self.branch,
                      'status': self.status}
        self.environment.add_override_attr('deployment', deployment)

    def build(self):
        """
        Saves deployment for restore after build
        """
        super(ChefRazorDeployment, self).build()
        self.save_to_environment()

    def update_environment(self):
        """
        Saves deployment for restore after update environment
        """
        super(ChefRazorDeployment, self).update_environment()
        self.save_to_environment()

    def free_node(self, image, environment):
        """
        Provides a free node from
        """
        nodes = self.node_search("name:qa-%s-pool*" % image)
        for node in nodes:
            is_default = node.chef_environment == "_default"
            iface_in_run_list = "recipe[network-interfaces]" in node.run_list
            if (is_default and iface_in_run_list):
                node.chef_environment = environment.name
                node['in_use'] = "provisioned"
                node.save()
                return node
        raise Exception("No more nodes!!")
        self.destroy()

    @classmethod
    def fromfile(cls, name, branch, config, path=None):
        """
        Returns a new deployment given a deployment template at path
        """
        if not path:
            path = os.path.join(os.path.dirname(__file__),
                                os.pardir,
                                'deployment_templates/default.yaml')
        local_api = autoconfigure()

        if Environment('name', api=local_api).exists:
            # Use previous dry build if exists
            return cls.from_chef_environment(name, config, path)

        template = Config(path)[name]

        chef = Chef(name, local_api, description=name)
        razor = razor_api(config['razor']['ip'])
        os_name = template['os']
        product = template['product']
        name = template['name']

        deployment = cls.deployment_config(template['os-features'],
                                           template['rpcs-features'], name,
                                           os_name, branch, config, chef,
                                           razor)
        for features in template['nodes']:
            node = deployment.node_config(features, os_name, product, chef,
                                          razor, branch)
            deployment.nodes.append(node)

        return deployment

    @classmethod
    def from_chef_environment(cls, environment, config=None, path=None):
        """
        Rebuilds a Deployment given a chef environment
        """
        if not config:
            config = Config()
        if not path:
            path = os.path.join(os.path.dirname(__file__),
                                os.pardir,
                                'deployment_templates/default.yaml')
        local_api = autoconfigure()
        env = Environment(environment, api=local_api)
        deployment_args = env.override_attributes['deployment']
        override = env.override_attributes
        default = env.default_attributes
        chef = Chef(env.name, local_api, description=env.name, default=default,
                    override=override)
        deployment_args['chef'] = chef
        razor = razor_api(config['razor']['ip'])
        deployment_args['razor'] = razor
        deployment_args['config'] = config
        nodes = deployment_args.pop('nodes')
        deployment = cls.deployment_config(**deployment_args)
        template = Config(path)[environment]
        product = template['product']
        for node in (Node(n) for n in nodes):
            crnode = ChefRazorNode.from_chef_node(node,
                                                  deployment_args['os_name'],
                                                  product, chef,
                                                  deployment, razor,
                                                  deployment_args['branch'])
            deployment.nodes.append(crnode)
        deployment.save_to_environment()
        return deployment

    # NOTE: This probably should be in node instead and use from_chef_node
    def node_config(self, features, os_name, product, chef, razor,
                    branch):
        """
        Returns node from free node given a dictionary of features
        """
        cnode = self.free_node(os_name, chef)
        node = ChefRazorNode.from_chef_node(cnode, os_name, product, chef,
                                            self, razor, branch)
        node.add_features(features)
        return node

    @classmethod
    def deployment_config(cls, os_features, rpcs_features, name, os_name,
                          branch, config, chef, razor, status="provisioning"):
        """
        Returns deployment given dictionaries of features
        """
        deployment = cls(name, os_name, branch, config, chef,
                         razor)
        deployment.add_features(os_features)
        if rpcs_features:
            deployment.add_features(rpcs_features)
        deployment.save_to_environment()
        return deployment

    def add_features(self, features):
        """
        Adds a dictionary of features as strings to deployment

        ex: {"monitoring": "default", "glance": "cf", ...}
        """
        # stringify and lowercase classes in deployment features
        classes = {k.lower(): v for (k, v) in
                   getmembers(deployment_features, isclass)}
        for feature, rpcs_feature in features.items():
            self.features.append(classes[feature](self, rpcs_feature))

    @classmethod
    def node_search(cls, query, environment=None, tries=10):
        """
        Performs a node search query on the chef server
        """
        api = autoconfigure()
        if environment:
            api = environment.local_api
        search = None
        while not search and tries > 0:
            search = Search("node", api=api).query(query)
            sleep(10)
            tries = tries - 1
        return (n.object for n in search)

    def search_role(self, feature):
        """
        Returns nodes the have the desired role
        """
        return (node for node in
                self.nodes if feature in
                (str(f).lower() for f in node.features))

    def destroy(self):
        """
        Destroys ChefRazor Deployment
        """
        self.status = "Destroying"
        # Nullify remote api so attributes are not sent remotely
        self.environment.remote_api = None
        super(ChefRazorDeployment, self).destroy()
        self.environment.destroy()
        self.status = "Destroyed"

    def __str__(self):
        nodes = "\n\t".join(str(node) for node in self.nodes)
        deployment = ("Deployment - name:{0}, os:{1}, branch:{2}, status:{3}\n"
                      "{4}\nNodes:\n\t{5}".format(self.name, self.os_name,
                                                  self.branch, self.status,
                                                  self.environment, nodes))
        return deployment

    def openrc(self):
        user_name = self.environment.override_attributes['keystone'][
            'admin_user']
        user = self.environment.override_attributes['keystone']['users'][
            user_name]
        password = user['password']
        tenant = user['roles'].keys()[0]
        controller = next(self.search_role('controller'))
        url = Node(controller.name).normal['keystone']['publicURL']
        strategy = 'keystone'
        openrc = {'OS_USERNAME': user_name, 'OS_PASSWORD': password,
                  'OS_TENANT_NAME': tenant, 'OS_AUTH_URL': url,
                  'OS_AUTH_STRATEGY': strategy, 'OS_NO_CACHE': '1'}
        for key in openrc.keys():
            os.putenv(key, openrc[key])
        os.system(os.environ['SHELL'])

    def horizon_ip(self):
        controller = next(self.search_role('controller'))
        ip = controller.ipaddress
        if "vips" in self.environment.override_attributes:
            ip = self.environment.override_attributes['vips']['nova-api']
        return ip
