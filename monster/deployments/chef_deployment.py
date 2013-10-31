import os

from chef import autoconfigure, Environment, Node

from monster import util
from monster.Environments import Chef
from monster.config import Config
from monster.deployments.deployment import Deployment
from monster.features import deployment_features
from monster.features.node_features import ChefServer
from monster.nodes.chef_node import ChefNode
from monster.provisioners.provisioner import ChefRazorProvisioner


class ChefDeployment(Deployment):
    """ Deployment mechinisms specific to deployment using:
    Opscode's Chef as configuration management
    """

    def __init__(self, name, os_name, branch, environment, provisioner,
                 status=None):
        status = status or "provisioning"
        super(ChefDeployment, self).__init__(name, os_name, branch,
                                             provisioner, status)
        self.environment = environment
        self.has_controller = False

    def __str__(self):
        nodes = "\n\t".join(str(node) for node in self.nodes)
        features = ", ".join(self.feature_names())
        deployment = ("Deployment - name:{0}, os:{1}, branch:{2}, status:{3}\n"
                      "{4}\nFeatures{5}: \n"
                      "Nodes: \n\t{6}".format(self.name, self.os_name,
                                              self.branch, self.status,
                                              self.environment, features,
                                              nodes))
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

    @classmethod
    def fromfile(cls, name, branch, provisioner, path=None):
        """
        Returns a new deployment given a deployment template at path
        """
        if not path:
            path = os.path.join(os.path.dirname(__file__),
                                os.pardir, os.pardir,
                                'deployment_templates/default.yaml')
        local_api = autoconfigure()

        if Environment(name, api=local_api).exists:
            # Use previous dry build if exists
            util.logger.info("Using previous deployment:{0}".format(name))
            return cls.from_chef_environment(name, path)

        template = Config(path)[name]

        environment = Chef(name, local_api, description=name)

        os_name = template['os']
        product = template['product']
        name = template['name']

        deployment = cls.deployment_config(template['features'], name, os_name,
                                           branch, environment, provisioner)
        for features in template['nodes']:
            deployment.node_config(features, os_name, product, environment,
                                   provisioner, branch)
        return deployment

    @classmethod
    def from_chef_environment(cls, environment, path=None,
                              provisioner=None):
        """
        Rebuilds a Deployment given a chef environment
        """
        if not path:
            path = os.path.join(os.path.dirname(__file__),
                                os.pardir, os.pardir,
                                'deployment_templates/default.yaml')
        local_api = autoconfigure()
        env = Environment(environment, api=local_api)
        override = env.override_attributes
        default = env.default_attributes
        chef_auth = override.get('remote_chef', None)
        remote_api = None
        if chef_auth:
            remote_api = ChefServer._remote_chef_api(chef_auth)
        environment = Chef(env.name, local_api, description=env.name,
                           default=default, override=override,
                           remote_api=remote_api)

        name = env.name
        deployment_args = override.get('deployment', {})
        features = deployment_args.get('features', {})
        os_name = deployment_args.get('os_name', None)
        branch = deployment_args.get('branch', None)
        status = deployment_args.get('status', "provisioning")
        deployment = cls.deployment_config(features, name, os_name, branch,
                                           environment, provisioner, status)

        nodes = deployment_args.get('nodes', [])
        template = Config(path)[env.name]
        product = template['product']
        for node in (Node(n, environment.local_api) for n in nodes):
            cnode = ChefNode.from_chef_node(node, deployment_args['os_name'],
                                            product, environment, deployment,
                                            provisioner,
                                            deployment_args['branch'])
            deployment.nodes.append(cnode)
        return deployment

    # NOTE: This probably should be in node instead and use from_chef_node
    def node_config(self, features, os_name, product, environment, provisioner,
                    branch):
        """
        Builds a new node given a dictionary of features
        """
        cnode = provisioner.available_node(os_name, self)
        node = ChefNode.from_chef_node(cnode, os_name, product, environment,
                                       self, provisioner, branch)
        self.nodes.append(node)
        node.add_features(features)

    @classmethod
    def deployment_config(cls, features, name, os_name, branch, environment,
                          provisioner, status=None):
        """
        Returns deployment given dictionaries of features
        """
        status = status or "provisioning"
        deployment = cls(name, os_name, branch, environment,
                         provisioner, status)
        deployment.add_features(features)
        return deployment

    def add_features(self, features):
        """
        Adds a dictionary of features as strings to deployment

        ex: {"monitoring": "default", "glance": "cf", ...}
        """
        # stringify and lowercase classes in deployment features
        classes = util.module_classes(deployment_features)
        for feature, rpcs_feature in features.items():
            util.logger.debug("feature: {0}, rpcs_feature: {1}".format(
                feature, rpcs_feature))
            self.features.append(classes[feature](self, rpcs_feature))

    def destroy(self):
        """
        Destroys Chef Deployment
        """
        self.status = "Destroying"
        # Nullify remote api so attributes are not sent remotely
        self.environment.remote_api = None
        super(ChefDeployment, self).destroy()
        # Destroy rogue nodes
        if not self.nodes:
            nodes = ChefRazorProvisioner.node_search("chef_environment:{0}".
                                                     format(self.name),
                                                     tries=1)
            for n in nodes:
                ChefNode.from_chef_node(n, environment=self.environment).\
                    destroy()

        # Destroy Chef environment
        self.environment.destroy()
        self.status = "Destroyed"

    def openrc(self):
        """
        Opens a new shell with variables loaded for novaclient
        """
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
        """
        Returns ip of horizon
        """
        controller = next(self.search_role('controller'))
        ip = controller.ipaddress
        if "vips" in self.environment.override_attributes:
            ip = self.environment.override_attributes['vips']['nova-api']
        return ip
