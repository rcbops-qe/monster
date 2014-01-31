
class Upgrade(object):
    """
    Base upgrade class
    """

    def __init__(self, deployment):
        self.deployment = deployment

    def upgrade(self, rc=False):
        raise NotImplementedError

    def update_environment(self):
        """
        Updates the deployments environment
        """

        self.deployment.environment.save()
