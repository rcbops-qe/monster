import os

from time import sleep
from chef import autoconfigure, Search, Environment, Node
from inspect import getmembers, isclass

from monster import util
from monster.Config import Config
from monster.razor_api import razor_api
from monster.Environments import Chef
from monster.nodes.chef_razor_node import ChefRazorNode
import monster.Features.Deployment as deployment_features
from monster.deployments.deployment import Deployment


class ChefDeployment(Deployment):
    """ Deployment mechinisms specific to deployment using:
    Opscode's Chef as configuration management
    """

    def __init__(self, name, os_name, branch, config, environment,
                 status="provisioning"):
        super(ChefDeployment, self).__init__(name, os_name, branch,
                                             config, status=status)
        self.environment = environment
        self.has_controller = False

    def __str__(self):
        nodes = "\n\t".join(str(node) for node in self.nodes)
        deployment = ("Deployment - name:{0}, os:{1}, branch:{2}, status:{3}\n"
                      "{4}\nNodes:\n\t{5}".format(self.name, self.os_name,
                                                  self.branch, self.status,
                                                  self.environment, nodes))
        return deployment

    def save_to_environment(self):
        """
        Save deployment restore attributes to chef environment
        """
        features = {key: value for (key, value) in
                    ((str(x).lower(), x.rpcs_feature) for x in self.features)}
        nodes = [n.name for n in self.nodes]
        deployment = {'nodes': nodes,
                      'features': features,
                      'name': self.name,
                      'os_name': self.os_name,
                      'branch': self.branch,
                      'status': self.status}
        self.environment.add_override_attr('deployment', deployment)

    def build(self):
        """
        Saves deployment for restore after build
        """
        super(ChefDeployment, self).build()
        self.save_to_environment()

    def update_environment(self):
        """
        Saves deployment for restore after update environment
        """
        super(ChefDeployment, self).update_environment()
        self.save_to_environment()

    # move this into provisioner plugin
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
        self.destroy()
        raise Exception("No more nodes!!")

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

        os_name = template['os']
        product = template['product']
        name = template['name']

        deployment = cls.deployment_config(template['features'], name,
                                           os_name, branch, config, chef)
        razor = razor_api(config['razor']['ip'])
        for features in template['nodes']:
            deployment.node_config(features, os_name, product, chef,
                                   razor, branch)
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
            ChefRazorNode.from_chef_node(node, deployment_args['os_name'],
                                         product, chef, deployment, razor,
                                         deployment_args['branch'])
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
        self.nodes.append(node)
        node.add_features(features)

    @classmethod
    def deployment_config(cls, features, name, os_name,
                          branch, config, chef, razor, status="provisioning"):
        """
        Returns deployment given dictionaries of features
        """
        deployment = cls(name, os_name, branch, config, chef,
                         razor)
        deployment.add_features(features)
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
            util.logger.debug("feature: {0}, rpcs_feature: {1}".format(
                feature, rpcs_feature))
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

    def destroy(self):
        """
        Destroys Chef Deployment
        """
        self.status = "Destroying"
        # Nullify remote api so attributes are not sent remotely
        self.environment.remote_api = None
        super(ChefDeployment, self).destroy()
        # Destroy rogue nodes
        nodes = self.node_search("chef_environment:{0}".format(self.name),
                                 tries=1)
        for n in nodes:
            ChefRazorNode.from_chef_node(n, provisioner=self.razor).destroy()
        # Destroy Chef environment
        self.environment.destroy()
        self.status = "Destroyed"

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
