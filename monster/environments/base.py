import logging

logger = logging.getLogger(__name__)


class Environment(dict):

    def __init__(self, name, description=""):
        super(Environment, self).__init__()
        self.name = name
        self.description = description

    @property
    def _local_env(self):
        raise NotImplementedError()

    @property
    def _remote_env(self):
        raise NotImplementedError()

    def save(self):
        raise NotImplementedError()

    def save_remote_to_local(self):
        raise NotImplementedError()

    def save_env_to_local_and_to_remote(self, env):
        raise NotImplementedError()

    def destroy(self):
        raise NotImplementedError()

    @property
    def deployment_attributes(self):
        raise NotImplementedError()

    @property
    def features(self):
        raise NotImplementedError()

    @property
    def branch(self):
        raise NotImplementedError()

    @property
    def os_name(self):
        raise NotImplementedError()

    @property
    def nodes(self):
        raise NotImplementedError()

    @property
    def provisioner(self):
        raise NotImplementedError()

    @property
    def product(self):
        raise NotImplementedError()

    @property
    def is_high_availability(self):
        raise NotImplementedError()

    @property
    def rabbit_mq_queue_ip(self):
        raise NotImplementedError()
