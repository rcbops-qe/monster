from chef import Environment as ChefEnvironment

from monster.environments.base_environment_wrapper import \
    BaseEnvironmentWrapper, logger


class ChefEnvironmentWrapper(BaseEnvironmentWrapper):

    def __init__(self, name, local_api, remote_api=None, chef_server_name=None,
                 description='', default=None, override=None):
        super(ChefEnvironmentWrapper,
              self).__init__(name=name, local_api=local_api,
                             remote_api=remote_api, description=description,
                             default=default, override=override)
        self.cookbook_versions = {}
        self.json_class = "Chef::Environment"
        self.chef_type = "environment"
        self.chef_server_name = chef_server_name
        self.save()

    def __repr__(self):
        """(Excludes unserializable chef objects.)"""

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

    @property
    def _local_env(self):
        if self.local_api:
            return ChefEnvironment(self.name, self.local_api)
        else:
            return None

    @property
    def _remote_env(self):
        if self.remote_api:
            return ChefEnvironment(self.name, self.remote_api)
        else:
            return None

    def save(self):
        env = self._local_env
        self._update_env_with_local_object_info(env)
        self.save_env_to_local_and_to_remote(env)

    def save_remote_to_local(self):
        if self.remote_api:
            env = self._remote_env
            self.override_attributes = env.override_attributes
            self.default_attributes = env.default_attributes
            self.save()

    def save_env_to_local_and_to_remote(self, env):
        env.save(self.local_api)
        if self.remote_api:
            try:
                env.save(self.remote_api)
            except Exception as e:
                logger.error("Remote env error:{0}".format(e))

    def _update_env_with_local_object_info(self, env):
        for attr in self.__dict__:
            logger.debug("{0}: {1}".format(attr, self.__dict__[attr]))
            setattr(env, attr, self.__dict__[attr])

    def destroy(self):
        self._local_env.delete()

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
