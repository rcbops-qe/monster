import logging

import chef
import monster.nodes.chef_.node as chef_node_wrapper
import monster.features.node_features as node_features
import monster.environments.chef_.environment as wrapper
import monster.orchestrator.base as base
import monster.deployments.rpcs.deployment as rpcs
import monster.config as config
import monster.provisioners.util as provisioner_util


logger = logging.getLogger(__name__)


class Orchestrator(base.Orchestrator):
    def create_deployment_from_file(self, name, template, branch,
                                    provisioner_name):
        """Returns a new deployment given a deployment template at path.
        :param name: name for the deployment
        :type name: str
        :param name: name of template to use
        :type name: str
        :param branch: branch of the RCBOPS chef cookbook repo to use
        :type branch:: str
        :param provisioner_name: provisioner to use for nodes
        :type provisioner_name: str
        :rtype: Deployment
        """
        logger.info("Building deployment object for {0}".format(name))
        provisioner = provisioner_util.get_provisioner(provisioner_name)

        if chef.Environment(name, api=self.local_api).exists:
            logger.info("Using previous deployment:{0}".format(name))
            return self.load_deployment_from_name(name)

        environment = wrapper.Environment(name=name, local_api=self.local_api,
                                          description=name)

        template = config.fetch_template(template, branch)

        os, product, features = template.fetch('os', 'product', 'features')

        deployment = rpcs.Deployment(name, os, branch, environment,
                                     provisioner, "provisioning", product,
                                     features=features)

        deployment.nodes = provisioner.build_nodes(template, deployment,
                                                   chef_node_wrapper)
        return deployment

    def load_deployment_from_name(self, name):
        """Rebuilds a Deployment given a deployment name.
        :param name: name of deployment
        :type name: string
        :rtype: Deployment
        """
        default, override, remote_api = self.load_environment_attributes(name)
        env = wrapper.Environment(name=name, local_api=self.local_api,
                                  remote_api=remote_api, description=name,
                                  default_attributes=default,
                                  override_attributes=override)

        provisioner = provisioner_util.get_provisioner(env.provisioner)

        deployment = rpcs.Deployment(name, env.os_name, env.branch, env,
                                     provisioner, "provisioning", env.product,
                                     features=env.features)

        deployment.nodes = provisioner.load_nodes(env, deployment,
                                                  chef_node_wrapper)
        return deployment

    def load_environment_attributes(self, name):
        local_env = chef.Environment(name, self.local_api)
        chef_auth = local_env.override_attributes.get('remote_chef', None)

        if chef_auth and chef_auth['key']:
            remote_api = node_features.ChefServer.remote_chef_api(chef_auth)
            remove_env = chef.Environment(name, remote_api)
            default = remove_env.default_attributes
            override = remove_env.override_attributes
        else:
            remote_api = None
            default = local_env.default_attributes
            override = local_env.override_attributes

        return default, override, remote_api

    @property
    def local_api(self):
        return chef.autoconfigure()
