import os

from chef import autoconfigure
from chef import Node as ChefNode
from chef import Environment as ChefEnvironment

from fabric.api import *

from monster import util
from monster.config import Config
from monster.features.node_feature import ChefServer
from monster.provisioners.util import get_provisioner
from monster.nodes.chef_node import Chef as MonsterChefNode
from monster.deployments.chef_deployment import ChefDeployment
from monster.environments.chef_environment import Chef as \
    MonsterChefEnvironment


class Orchestrator:
    def __init__(self):
        pass

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
            util.logger.info("Using previous deployment:{0}".format(name))
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
            util.logger.critical("Looking for the template {0} in the file: "
                                 "\n{1}\n The key was not found!"
                                 .format(template, path))
            exit(1)

        environment = MonsterChefEnvironment(name, local_api, description=name)

        os_name = template['os']
        product = template['product']

        deployment = Orchestrator.deployment_config(template['features'], name,
                                                    os_name, branch,
                                                    environment, provisioner,
                                                    product=product)

        # provision nodes
        chef_nodes = provisioner.provision(template, deployment)
        for node in chef_nodes:
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

    @staticmethod
    def from_chef_environment(environment):
        """
        Rebuilds a Deployment given a chef environment
        :param environment: name of environment
        :type environment: string
        :rtype: Chef
        """

        local_api = autoconfigure()
        environ = ChefEnvironment(environment, api=local_api)
        if not environ.exists:
            util.logger.error("The specified environment, {0}, does not"
                              "exist.".format(environment))
            exit(1)
        override = environ.override_attributes
        default = environ.default_attributes
        chef_auth = override.get('remote_chef', None)
        remote_api = None
        if chef_auth and chef_auth["key"]:
            remote_api = ChefServer._remote_chef_api(chef_auth)
            renv = ChefEnvironment(environment, api=remote_api)
            override = renv.override_attributes
            default = renv.default_attributes
        environment = MonsterChefEnvironment(
            environ.name, local_api, description=environ.name,
            default=default, override=override, remote_api=remote_api)

        name = environ.name
        deployment_args = override.get('deployment', {})
        features = deployment_args.get('features', {})
        os_name = deployment_args.get('os_name', None)
        branch = deployment_args.get('branch', None)
        status = deployment_args.get('status', "provisioning")
        product = deployment_args.get('product', None)
        provisioner_name = deployment_args.get('provisioner', "razor2")
        provisioner = get_provisioner(provisioner_name)

        deployment = Orchestrator.deployment_config(features, name, os_name,
                                                    branch, environment,
                                                    provisioner, status,
                                                    product=product)

        nodes = deployment_args.get('nodes', [])
        for node in (ChefNode(n, local_api) for n in nodes):
            if not node.exists:
                util.logger.error("Non existant chef node:{0}".
                                  format(node.name))
                continue
            cnode = MonsterChefNode.from_chef_node(node, product, environment,
                                                   deployment, provisioner,
                                                   deployment_args['branch'])
            deployment.nodes.append(cnode)
        return deployment

    @staticmethod
    def deployment_config(features, name, os_name, branch, environment,
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
        deployment = ChefDeployment(name, os_name, branch, environment,
                                    provisioner, status, product)
        deployment.add_features(features)
        return deployment
