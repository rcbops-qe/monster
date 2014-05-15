class Orchestrator:

    @property
    def local_api(self):
        raise NotImplementedError

    def create_deployment_from_file(self, name):
        """Returns a new deployment given a deployment template at path.
        :param name: name for the deployment
        :type name: str
        :rtype: Deployment
        """
        raise NotImplementedError

    def load_deployment_from_name(self, name):
        """Rebuilds a Deployment given a deployment name.
        :param name: name of deployment
        :type name: string
        :rtype: Deployment
        """
        raise NotImplementedError
