class DeploymentOrchestrator:

    @property
    def local_api(self):
        raise NotImplementedError

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
        raise NotImplementedError

    def load_deployment_from_name(self, environment):
        """Rebuilds a Deployment given a deployment name.
        :param environment: name of deployment
        :type environment: string
        :rtype: Deployment
        """
        raise NotImplementedError
