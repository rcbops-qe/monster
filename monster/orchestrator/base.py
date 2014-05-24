class Orchestrator:

    def create_deployment_from_file(self, name):
        """Returns a new deployment given a deployment template at path.
        :param name: name for the deployment
        :type name: str
        :rtype: Deployment
        """
        raise NotImplementedError
