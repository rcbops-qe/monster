import os
import sys
#import threading

from chef import autoconfigure
from chef import Node as ChefNode
from chef import Environment as ChefEnvironment

from fabric.api import *
from fabric.state import env
from threading import Thread

from monster import util
from monster.util import Logger
from monster.config import Config
from monster.upgrades.util import int2word
from monster.features.node import ChefServer
from monster.provisioners.razor import Razor
from monster.clients.openstack import Creds, Clients
from monster.provisioners.util import get_provisioner
from monster.deployments.deployment import Deployment
from monster.nodes.chef_node import Chef as MonsterChefNode
from monster.features import deployment as deployment_features
from monster.environments.chef_environment import Chef as \
    MonsterChefEnvironment


logger = Logger("monster.deployments.chef_deployment")


class Chef(Deployment):
    """
    Deployment mechanisms specific to deployment using
    Opscode's Chef as configuration management
    """

    def __init__(self, name, os_name, branch, environment, provisioner,
                 status=None, product=None, clients=None):
        status = status or "provisioning"
        super(Chef, self).__init__(name, os_name, branch,
                                   provisioner, status, product,
                                   clients)
        self.environment = environment
        self.has_controller = False
        self.has_orch_master = False
        logger.set_log_level()

    def __str__(self):
        nodes = "\n\t".join(str(node) for node in self.nodes)
        features = ", ".join(self.feature_names)
        deployment = ("Deployment - name:{0}, os:{1}, branch:{2}, status:{3}\n"
                      "{4}\nFeatures: \n\t{5}\n"
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
                      'status': self.status,
                      'product': self.product,
                      'provisioner': self.provisioner}
        self.environment.add_override_attr('deployment', deployment)

    def build(self):
        """
        Saves deployment for restore after build
        """

        super(Chef, self).build()
        self.save_to_environment()

    def get_upgrade(self, upgrade):
        """
        This will return an instance of the correct upgrade class
        :param upgrade: The name of the provisoner
        :type upgrade: String
        :rtype: object
        """

        # convert branch into a list of int strings
        if 'v' in upgrade:
            branch_i = [int(x) for x in upgrade.strip('v').split('.')]
        else:
            branch_i = [int(x) for x in upgrade.split('.')]

        # convert list of int strings to their english counterpart
        word_b = [int2word(b) for b in branch_i]

        # convert list to class name
        up_class = "".join(word_b).replace(" ", "")
        up_class_module = "_".join(word_b).replace(" ", "")

        try:
            identifier = getattr(sys.modules['monster'].upgrades,
                                 up_class_module)
        except AttributeError:
            raise NameError("{0} doesn't exist.".format(up_class_module))

        return util.module_classes(identifier)[up_class](self)

    def upgrade(self, upgrade_branch):
        """
        Upgrades the deployment (very chefy, rcbopsy)
        """

        rc = False

        # if we are deploying a release candidate upgrade
        if "rc" in upgrade_branch:
            upgrade_branch = upgrade_branch.rstrip("rc")
            rc = True

        upgrade = self.get_upgrade(upgrade_branch)
        upgrade.upgrade(rc)

    def update_environment(self):
        """
        Saves deployment for restore after update environment
        """

        super(Chef, self).update_environment()
        self.save_to_environment()
        with open("{0}.json".format(self.name), "w") as f:
            f.write(str(self.environment))

    @classmethod
    def fromfile(cls, name, template, branch, provisioner, template_path):
        """
        Returns a new deployment given a deployment template at path
        :param name: name for the deployment
        :type name: string
        :param name: name of template to use
        :type name: string
        :param branch: branch of the RCBOPS chef cookbook repo to use
        :type branch:: string
        :param provisioner: provisioner to use for nodes
        :type provisioner: Provisioner
        :param path: path to template
        :type path: string
        :rtype: Chef
        """
        local_api = autoconfigure()

        template_file = ""
        if branch == "master":
            template_file = "default"
        else:
            template_file = branch.lstrip('v')
            if "rc" in template_file:
                template_file = template_file.rstrip("rc")
            template_file = template_file.replace('.', '_')

        if ChefEnvironment(name, api=local_api).exists:
            # Use previous dry build if exists
            logger.info("Using previous deployment:{0}".format(name))
            return cls.from_chef_environment(name)
        path = ""
        if not template_path:
            path = os.path.join(os.path.dirname(__file__),
                                os.pardir, os.pardir,
                                'templates/{0}.yaml'.format(
                                    template_file))
        else:
            path = template_path
        try:
            template = Config(path)[template]
        except KeyError:
            logger.critical("Looking for the template {0} in the file: "
                            "\n{1}\n The key was not found!"
                            .format(template, path))
            exit(1)

        environment = MonsterChefEnvironment(name, local_api, description=name)

        os_name = template['os']
        product = template['product']

        deployment = cls.deployment_config(template['features'], name, os_name,
                                           branch, environment, provisioner,
                                           product=product)

        # provision nodes
        chef_nodes = provisioner.provision(template, deployment)
#        threads = []
#        from time import sleep
        for node in chef_nodes:
#            cnode = MonsterChefNode.from_chef_node(node, product, environment,
#                                                   deployment, provisioner,
#                                                   branch)
#            deployment.nodes.append(cnode)
#            tx = Thread(target=cls.provision_nodes,
#                        args=(provisioner, cnode, ))
#            threads.append(tx)
#            tx.start()
#            sleep(2)


            cnode = MonsterChefNode.from_chef_node(node, product, environment,
                                                   deployment, provisioner,
                                                   branch)
            provisioner.post_provision(cnode)
            deployment.nodes.append(cnode)
#        for tx in threads:
#            tx.join()
        # add features
        for node, features in zip(deployment.nodes, template['nodes']):
            node.add_features(features)

        return deployment

#    @classmethod
#    def provision_nodes(cls, provisioner, cnode):
#        provisioner.post_provision(cnode)

    @classmethod
    def from_chef_environment(cls, environment):
        """
        Rebuilds a Deployment given a chef environment
        :param environment: name of environment
        :type environment: string
        :rtype: Chef
        """

        local_api = autoconfigure()
        env = ChefEnvironment(environment, api=local_api)
        if not env.exists:
            logger.error("The specified environment, {0}, does not"
                         "exist.".format(environment))
            exit(1)
        override = env.override_attributes
        default = env.default_attributes
        chef_auth = override.get('remote_chef', None)
        remote_api = None
        if chef_auth and chef_auth["key"]:
            remote_api = ChefServer._remote_chef_api(chef_auth)
            renv = ChefEnvironment(environment, api=remote_api)
            override = renv.override_attributes
            default = renv.default_attributes
        environment = MonsterChefEnvironment(
            env.name, local_api, description=env.name,
            default=default, override=override, remote_api=remote_api)

        name = env.name
        deployment_args = override.get('deployment', {})
        features = deployment_args.get('features', {})
        os_name = deployment_args.get('os_name', None)
        branch = deployment_args.get('branch', None)
        status = deployment_args.get('status', "provisioning")
        product = deployment_args.get('product', None)
        provisioner_name = deployment_args.get('provisioner', "razor2")
        provisioner = get_provisioner(provisioner_name)

        deployment = cls.deployment_config(features, name, os_name, branch,
                                           environment, provisioner, status,
                                           product=product)

        nodes = deployment_args.get('nodes', [])
        for node in (ChefNode(n, local_api) for n in nodes):
            if not node.exists:
                logger.error("Non existant chef node:{0}".
                             format(node.name))
                continue
            cnode = MonsterChefNode.from_chef_node(node, product, environment,
                                                   deployment, provisioner,
                                                   deployment_args['branch'])
            deployment.nodes.append(cnode)
        return deployment

    @classmethod
    def deployment_config(cls, features, name, os_name, branch, environment,
                          provisioner, status=None, product=None):
        """
        Returns deployment given dictionaries of features
        :param features: dictionary of features {"monitoring": "default", ...}
        :type features: dict
        :param name: name of deployment
        :type name: string
        :param os_name: name of operating system
        :type os_name: string
        :param branch: branch of rcbops chef cookbooks to use
        :type branch: string
        :param environment: ChefEnvironment for deployment
        :type environment: ChefEnvironment
        :param provisioner: provisioner to deploy nodes
        :type provisioner: Provisioner
        :param status: initial status of deployment
        :type status: string
        :param product: name of rcbops product - compute, storage
        :type product: string
        :rtype: Chef
        """

        status = status or "provisioning"
        deployment = cls(name, os_name, branch, environment,
                         provisioner, status, product)
        deployment.add_features(features)
        return deployment

    def add_features(self, features):
        """
        Adds a dictionary of features to deployment
        :param features: dictionary of features {"monitoring": "default", ...}
        :type features: dict
        """

        # stringify and lowercase classes in deployment features
        classes = util.module_classes(deployment_features)
        for feature, rpcs_feature in features.items():
            logger.debug("feature: {0}, rpcs_feature: {1}".format(
                feature, rpcs_feature))
            self.features.append(classes[feature](self, rpcs_feature))

    def destroy(self):
        """
        Destroys Chef Deployment
        """

        self.status = "Destroying"
        # Nullify remote api so attributes are not sent remotely
        self.environment.remote_api = None
        super(Chef, self).destroy()
        # Destroy rogue nodes
        if not self.nodes:
            nodes = Razor.node_search("chef_environment:{0}".
                                      format(self.name),
                                      tries=1)
            for n in nodes:
                MonsterChefNode.from_chef_node(n,
                                               environment=self.environment).\
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
        url = ChefNode(controller.name).normal['keystone']['publicURL']
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
        :rtype: String
        """

        controller = next(self.search_role('controller'))
        ip = controller.ipaddress
        if "vips" in self.environment.override_attributes:
            ip = self.environment.override_attributes['vips']['nova-api']
        return ip

    @property
    def openstack_clients(self):
        """
        Setup openstack clients generator for deployment
        """

        override = self.environment.override_attributes
        keystone = override['keystone']
        users = keystone['users']
        user = keystone['admin_user']
        region = "RegionOne"
        password = users[user]["password"]
        tenant_name = "admin"
        auth_url = "http://{0}:5000/v2.0".format(self.horizon_ip())
        creds = Creds(username=user, password=password, region=region,
                      auth_url=auth_url, project_id=tenant_name,
                      tenant_name=tenant_name)
        return Clients(creds)
