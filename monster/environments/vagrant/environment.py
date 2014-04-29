import monster.environments.base as base


logger = base.logger


class Environment(base.Environment):

    def __init__(self, name, description, local_api, remote_api=None,
                 default_attributes=None, override_attributes=None):
        """Initializes a Vagrant Environment wrapper."""
        super(Environment, self).__init__(name=name, description=description)
