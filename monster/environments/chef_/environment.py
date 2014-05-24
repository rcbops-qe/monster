import monster.environments.base as base
import chef

logger = base.logger


class Environment(base.Environment):

    def __init__(self, name, local_api, description="",
                 default_attributes=None, override_attributes=None,
                 cookbook_versions=None):
        """Initializes a Chef Environment wrapper."""
        super(Environment, self).__init__(name=name, description=description)
        self.local_api_dict = {"url": local_api.url,
                               "key": local_api.key.raw,
                               "client": local_api.client}

        self.default_attributes = default_attributes or {}
        self.override_attributes = override_attributes or {}
        self.cookbook_versions = cookbook_versions or {}
        self.json_class = "Chef::Environment"
        self.chef_type = "environment"

    def __repr__(self):
        """(Excludes unserializable chef objects.)"""

        chef_dict = {
            "name": self.name,
            "description": self.description,
            "default_attributes": self.default_attributes,
            "override_attributes": self.override_attributes,
            "cookbook_versions": self.cookbook_versions,
            "chef_type": self.chef_type,
            "json_class": self.json_class
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
    def _local_env(self):
        if self.local_api:
            return chef.Environment(self.name, self.local_api)
        else:
            return None

    @property
    def _remote_env(self):
        if self.remote_api:
            return chef.Environment(self.name, self.remote_api)
        else:
            return None

    @property
    def remote_api(self):
        if 'remote_chef' in self.override_attributes:
            return chef.ChefAPI(**self.override_attributes['remote_chef'])
        else:
            return None

    @property
    def local_api(self):
        return chef.ChefAPI(**self.local_api_dict)

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
