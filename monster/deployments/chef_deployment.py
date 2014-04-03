import os
import sys

from chef import Node as ChefNode

from fabric.api import *

from monster import util
from monster.upgrades.util import int2word
from monster.provisioners.razor import Razor
from monster.clients.openstack import Creds, Clients
from monster.deployments.deployment import Deployment
from monster.nodes.chef_node import Chef as MonsterChefNode
from monster.features import deployment_feature as deployment_features

from pyrabbit.api import Client as RabbitClient


class ChefDeployment(Deployment):
    """
    Deployment mechanisms specific to deployment using
    Opscode's Chef as configuration management
    """

    def __init__(self, name, os_name, branch, environment, provisioner,
                 status=None, product=None, clients=None):
        status = status or "provisioning"
        super(ChefDeployment, self).__init__(name, os_name, branch,
                                             provisioner, status, product,
                                             clients)
        self.environment = environment
        self.has_controller = False
        self.has_orch_master = False

    def __repr__(self):
        return {'nodes': self.nodes, 'features': self.features,
                'name': self.name, 'os_name': self.os_name,
                'branch': self.branch, 'status': self.status,
                'product': self.product, 'provisioner': self.provisioner}

    def __str__(self):
        return str(self.__repr__())

    def build(self):
        """
        Saves deployment for restore after build
        """

        super(ChefDeployment, self).build()
        self.save_to_environment()

    def save_to_environment(self):
        """
        Save deployment restore attributes to chef environment
        """

        features = {key: value for (key, value) in
                    ((str(x).lower(), x.rpcs_feature) for x in self.features)}
        nodes = [n.name for n in self.nodes]
        deployment = {'nodes': nodes,
                      'features': features,
                      'name': self.name,
                      'os_name': self.os_name,
                      'branch': self.branch,
                      'status': self.status,
                      'product': self.product,
                      'provisioner': self.provisioner}
        self.environment.add_override_attr('deployment', deployment)

    def get_upgrade(self, branch_name):
        """
        This will return an instance of the correct upgrade class
        :param branch_name: The name of the provisioner
        :type branch_name: str
        :rtype: object
        """

        # convert branch into a list of int strings
        branch_i = [int(x) for x in branch_name.lstrip('v').split('.')]

        # convert list of int strings to their english counterpart
        word_b = [int2word(b) for b in branch_i]

        # convert list to class name
        up_class = "".join(word_b).replace(" ", "")
        up_class_module = "_".join(word_b).replace(" ", "")

        try:
            identifier = getattr(sys.modules['monster'].upgrades,
                                 up_class_module)
        except AttributeError:
            raise NameError("{0} doesn't exist.".format(up_class_module))

        return util.module_classes(identifier)[up_class](self)

    def upgrade(self, branch_name):
        """
        Upgrades the deployment (very chefy, rcbopsy)
        """

        rc = "rc" in branch_name
        upgrade_branch_name = branch_name.rstrip("rc")

        upgrade = self.get_upgrade(upgrade_branch_name)
        upgrade.upgrade(rc)

    def update_environment(self):
        """
        Saves deployment for restore after update environment
        """

        super(ChefDeployment, self).update_environment()
        self.save_to_environment()
        with open("{0}.json".format(self.name), "w") as f:
            f.write(str(self.environment))

    def add_features(self, features):
        """
        Adds a dictionary of features to deployment
        :param features: dictionary of features {"monitoring": "default", ...}
        :type features: dict
        """
        # stringify and lowercase classes in deployment features
        classes = util.module_classes(deployment_features)
        for feature, rpcs_feature in features.items():
            util.logger.debug("feature: {0}, rpcs_feature: {1}".format(
                feature, rpcs_feature))
            self.features.append(classes[feature](self, rpcs_feature))

    def destroy(self):
        """
        Destroys Chef Deployment
        """

        self.status = "Destroying"
        # Nullify remote api so attributes are not sent remotely
        self.environment.remote_api = None
        super(ChefDeployment, self).destroy()
        # Destroy rogue nodes
        if not self.nodes:
            nodes = Razor.node_search("chef_environment:{0}".
                                      format(self.name),
                                      tries=1)
            for n in nodes:
                MonsterChefNode.from_chef_node(n,
                                               environment=self.environment). \
                    destroy()

        # Destroy Chef environment
        self.environment.destroy()
        self.status = "Destroyed"

    def openrc(self):
        """
        Opens a new shell with variables loaded for nova-client
        """

        user_name = self.environment.override_attributes['keystone'][
            'admin_user']
        user = self.environment.override_attributes['keystone']['users'][
            user_name]
        password = user['password']
        tenant = user['roles'].keys()[0]
        controller = next(self.search_role('controller'))
        url = ChefNode(controller.name).normal['keystone']['publicURL']
        strategy = 'keystone'
        openrc = {'OS_USERNAME': user_name, 'OS_PASSWORD': password,
                  'OS_TENANT_NAME': tenant, 'OS_AUTH_URL': url,
                  'OS_AUTH_STRATEGY': strategy, 'OS_NO_CACHE': '1'}
        for key in openrc.keys():
            os.putenv(key, openrc[key])
        os.system(os.environ['SHELL'])

    def horizon_ip(self):
        """
        Returns ip of horizon
        :rtype: String
        """

        controller = next(self.search_role('controller'))
        ip = controller.ipaddress
        if "vips" in self.environment.override_attributes:
            ip = self.environment.override_attributes['vips']['nova-api']
        return ip

    @property
    def openstack_clients(self):
        """
        Setup OpenStack clients generator for deployment
        """

        override = self.environment.override_attributes
        keystone = override['keystone']
        users = keystone['users']
        user = keystone['admin_user']
        region = "RegionOne"
        password = users[user]["password"]
        tenant_name = "admin"
        auth_url = "http://{0}:5000/v2.0".format(self.horizon_ip())
        creds = Creds(username=user, password=password, region=region,
                      auth_url=auth_url, project_id=tenant_name,
                      tenant_name=tenant_name)
        return Clients(creds)

    @property
    def rabbitmq_mgmt_client(self):
        """
        Return rabbitmq management client
        """
        overrides = self.environment.override_attributes
        if 'vips' in overrides:
            # HA
            ip = overrides['vips']['rabbitmq-queue']
        else:
            # Non HA
            controller = next(self.search_role("controller"))
            ip = controller.ipaddress
        url = "{ip}:15672".format(ip=ip)

        user = "guest"
        password = "guest"

        return RabbitClient(url, user, password)
