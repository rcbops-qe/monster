"""
Chef Environment
"""

from chef import Environment as ChefEnvironment
import logging


logger = logging.getLogger(__name__)


class ChefEnvironmentWrapper(dict):

    def __init__(self, name, local_api, chef_server_name=None, remote_api=None,
                 description='', default=None, override=None):
        super(ChefEnvironmentWrapper, self).__init__({})
        self.name = name
        self.description = description
        self.cookbook_versions = {}
        self.json_class = "Chef::Environment"
        self.chef_type = "environment"
        self.default_attributes = default or {}
        self.override_attributes = override or {}
        self.local_api = local_api
        self.remote_api = remote_api
        self.chef_server_name = chef_server_name
        self.save()

    def __repr__(self):
        """
        Exclude unserializable chef objects
        """

        chef_dict = {
            "chef_type": self.chef_type,
            "cookbook_versions": self.cookbook_versions,
            "description": self.description,
            "json_class": self.json_class,
            "name": self.name,
            "default_attributes": self.default_attributes,
            "override_attributes": self.override_attributes
        }
        return str(chef_dict)

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

    def save_locally(self):
        if self.remote_api:
            env = self._remote_chef_env
            self.override_attributes = env.override_attributes
            self.default_attributes = env.default_attributes
            self.save()

    def destroy(self):
        self._local_chef_env.delete()

    def save(self):
        env = self._local_chef_env
        self._update_chef_env_with_local_object_info(env)
        self._save_local_and_remote(env)

    def _update_chef_env_with_local_object_info(self, env):
        for attr in self.__dict__:
            logger.debug("{0}: {1}".format(attr, self.__dict__[attr]))
            setattr(env, attr, self.__dict__[attr])

    def _save_local_and_remote(self, env):
        env.save(self.local_api)
        if self.remote_api:
            try:
                env.save(self.remote_api)
            except Exception as e:
                logger.error("Remote env error:{0}".format(e))

    @property
    def _local_chef_env(self):
        if self.local_api:
            return ChefEnvironment(self.name, self.local_api)
        else:
            return None

    @property
    def _remote_chef_env(self):
        if self.remote_api:
            return ChefEnvironment(self.name, self.remote_api)
        else:
            return None

    @property
    def deployment_attributes(self):
        return self.override_attributes.get('deployment', {})

    @property
    def features(self):
        return self.deployment_attributes.get('features', {})

    @property
    def branch(self):
        return self.deployment_attributes.get('branch', None)

    @property
    def os_name(self):
        return self.deployment_attributes.get('os_name', None)

    @property
    def nodes(self):
        return self.deployment_attributes.get('nodes', [])

    @property
    def provisioner(self):
        return self.deployment_attributes.get('provisioner', "razor2")

    @property
    def product(self):
        return self.deployment_attributes.get('product', None)

    @property
    def is_high_availability(self):
        return 'vips' in self.override_attributes

    @property
    def rabbit_mq_queue_ip(self):
        try:
            ip = self.override_attributes['vips']['rabbitmq-queue']
        except KeyError:
            return None
        else:
            return ip
