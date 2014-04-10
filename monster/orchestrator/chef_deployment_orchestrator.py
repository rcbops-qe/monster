from chef import autoconfigure, Node, Environment

from monster import util
from monster.config import Config
from monster.orchestrator.deployment_orchestrator import DeploymentOrchestrator
from monster.nodes.node_wrapper_factory import ChefNodeWrapperFactory
from monster.provisioners.util import get_provisioner
from monster.features.node_feature import ChefServer
from monster.deployments.chef_deployment import ChefDeployment
from monster.environments.chef_environment_wrapper import \
    ChefEnvironmentWrapper

class ChefDeploymentOrchestrator(DeploymentOrchestrator):

    @property
    def local_api(self):
        return autoconfigure()

    def create_deployment_from_file(self, name, template, branch,
                                    provisioner_name):
        """
        Returns a new deployment given a deployment template at path
        :param name: name for the deployment
        :type name: string
        :param name: name of template to use
        :type name: string
        :param branch: branch of the RCBOPS chef cookbook repo to use
        :type branch:: string
        :param provisioner_name: provisioner to use for nodes
        :type provisioner_name: str
        :rtype: ChefDeployment
        """
        provisioner = get_provisioner(provisioner_name)

        util.logger.info("Building deployment object for {0}".format(name))

        if Environment(name, api=self.local_api).exists:
            # Use previous dry build if exists
            util.logger.info("Using previous deployment:{0}".format(name))
            return self.load_deployment_from_name(name)
        environment = ChefEnvironmentWrapper(name, self.local_api,
                                             description=name)
        template = Config.fetch_template(template, branch)

        os, product, features = template.fetch('os', 'product', 'features')

        deployment = ChefDeployment(name, os, branch, environment,
                                    provisioner, "provisioning", product,
                                    features=features)
        deployment.nodes = provisioner.build_nodes(template, deployment,
                                                   ChefNodeWrapperFactory)

        for node, features in zip(deployment.nodes, template['nodes']):
            node.add_features(features)

        return deployment

    def load_deployment_from_name(self, name):
        """
        Rebuilds a Deployment given a deployment name
        :param name: name of deployment
        :type name: string
        :rtype: ChefDeployment
        """
        environ = Environment(name, api=self.local_api)
        if not environ.exists:
            util.logger.error("The specified environment, {0}, does not"
                              "exist.".format(name))
            exit(1)
        override = environ.override_attributes
        default = environ.default_attributes
        chef_auth = override.get('remote_chef', None)
        remote_api = None
        if chef_auth and chef_auth["key"]:
            remote_api = ChefServer._remote_chef_api(chef_auth)
            renv = Environment(name, api=remote_api)
            override = renv.override_attributes
            default = renv.default_attributes

        env_name = environ.name
        deployment_args = override.get('deployment', {})
        features = deployment_args.get('features', {})
        os_name = deployment_args.get('os_name', None)
        branch = deployment_args.get('branch', None)
        product = deployment_args.get('product', None)
        provisioner_name = deployment_args.get('provisioner', "razor2")

        environment = ChefEnvironmentWrapper(
            environ.name, self.local_api, description=environ.name,
            default=default, override=override, remote_api=remote_api)
        from IPython import embed; embed()

        provisioner = get_provisioner(provisioner_name)

        deployment = ChefDeployment(env_name, os_name, branch, environment,
                                    provisioner, "provisioning", product)
        deployment.add_features(features)

        nodes = deployment_args.get('nodes', [])
        for node in (Node(n, self.local_api) for n in nodes):
            if not node.exists:
                util.logger.error("Non-existent chef node: {0}".
                                  format(node.name))
                continue
            chef_node = ChefNodeWrapperFactory.wrap_node(
                node, product, environment, deployment, provisioner,
                deployment_args["branch"])
            deployment.nodes.append(chef_node)
        return deployment
