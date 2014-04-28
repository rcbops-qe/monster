import logging


logger = logging.getLogger(__name__)


class BaseEnvironmentWrapper(dict):

    def __init__(self, name, local_api, remote_api=None,
                 description='', default=None, override=None):
        super(BaseEnvironmentWrapper, self).__init__({})
        self.name = name
        self.local_api = local_api
        self.remote_api = remote_api
        self.description = description
        self.default_attributes = default or {}
        self.override_attributes = override or {}
        self.save()

    def add_override_attr(self, key, value):
        self.override_attributes[key] = value
        self.save()

    def add_default_attr(self, key, value):
        self.default_attributes[key] = value
        self.save()

    def del_override_attr(self, key):
        del self.override_attributes[key]
        self.save()

    def del_default_attr(self, key):
        del self.default_attributes[key]
        self.save()

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
