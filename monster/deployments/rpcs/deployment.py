from functools import partial
import os
import sys
import webbrowser

import pyrabbit.api as rabbit
from monster import active as active
import monster.threading_iface

import monster.upgrades.util as upgrades_util
import monster.clients.openstack as openstack
import monster.deployments.base as base
from monster.utils.introspection import module_classes


class Deployment(base.Deployment):
    """Deployment mechanisms specific to a RPCS deployment using Chef as
    configuration management.
    """
    def __init__(self, name, environment, clients=None):

        """Initializes a RPCS deployment object.
        :type name: str
        :type environment: monster.environments.chef.environment.Environment
        """
        super(Deployment, self).__init__(name=name,
                                         environment=environment,
                                         status="provisioning",
                                         clients=clients)
        self.has_controller = False
        self.has_orch_master = False
        self.nodes = self.fetch_nodes()

    def __str__(self):
        return repr(self)

    def __repr__(self):
        return str(self.to_dict)

    @property
    def to_dict(self):
        return {'name': self.name, 'os_name': self.os_name,
                'branch': self.branch, 'status': self.status,
                'nodes': self.node_names, 'features': self.features_dict,
                'product': self.product, 'provisioner': self.provisioner_name}

    def fetch_nodes(self):
        active.node_names = set(self.node_names)
        func_list = [partial(self.provisioner.build_node, self, spec)
                     for spec in active.template['nodes']]
        nodes = monster.threading_iface.execute(func_list)
        assert nodes is not None
        return nodes

    def add_nodes(self, node_request):
        pass

    def get_upgrade(self, branch_name):
        """This will return an instance of the correct upgrade class.
        :param branch_name: The name of the provisioner
        :type branch_name: str
        :rtype: monster.deployments.base.Deployment
        """

        # convert branch into a list of int strings
        branch_i = [int(x) for x in branch_name.lstrip('v').split('.')]

        # convert list of int strings to their english counterpart
        word_b = [upgrades_util.int2word(b) for b in branch_i]

        # convert list to class name
        up_class = "".join(word_b).replace(" ", "")
        up_class_module = "_".join(word_b).replace(" ", "")

        try:
            identifier = getattr(sys.modules['monster'].upgrades,
                                 up_class_module)
        except AttributeError:
            raise NameError("{0} doesn't exist.".format(up_class_module))

        return module_classes(identifier)[up_class](self)

    def upgrade(self, branch_name):
        """Upgrades the deployment."""

        rc = "rc" in branch_name
        upgrade_branch_name = branch_name.rstrip("rc")

        upgrade = self.get_upgrade(upgrade_branch_name)
        upgrade.upgrade(rc)

    def destroy(self):
        """Destroys Chef Deployment."""
        self.status = "destroying"
        super(Deployment, self).destroy()
        # Destroy rogue nodes
        self.environment.destroy()
        self.status = "destroyed"

    def update_environment(self):
        """Saves deployment for restore after update environment."""
        super(Deployment, self).update_environment()
        self.save_to_environment()
    # make sure this works; changes have been made...

    def save_to_environment(self):
        """Save deployment restore attributes to chef environment."""
        deployment = self.to_dict
        self.environment.add_override_attr('deployment', deployment)

    def horizon(self):
        url = "https://{0}".format(self.horizon_ip)
        webbrowser.open_new_tab(url)

    def openrc(self):
        """Opens a new shell with variables loaded for nova-client."""
        strategy = 'keystone'
        keystone = self.override_attrs['keystone']
        url = keystone['publicURL']
        user = keystone['admin_user']
        password = keystone['users'][user]['password']
        tenant = keystone['users'][user]['roles'].keys()[0]
        openrc = {'OS_USERNAME': user, 'OS_PASSWORD': password,
                  'OS_TENANT_NAME': tenant, 'OS_AUTH_URL': url,
                  'OS_AUTH_STRATEGY': strategy, 'OS_NO_CACHE': '1'}
        for key in openrc.keys():
            os.putenv(key, openrc[key])
        os.system(os.environ['SHELL'])

    @property
    def openstack_clients(self):
        """Setup OpenStack clients generator for deployment."""
        keystone = self.override_attrs['keystone']
        user = keystone['admin_user']
        password = keystone['users'][user]["password"]
        region = "RegionOne"
        tenant_name = "admin"
        auth_url = "http://{0}:5000/v2.0".format(self.horizon_ip)

        creds = openstack.Creds(username=user, password=password,
                                region=region, auth_url=auth_url,
                                project_id=tenant_name,
                                tenant_name=tenant_name)

        return openstack.Clients(creds)

    @property
    def rabbitmq_mgmt_client(self):
        """Return rabbitmq management client."""
        if self.environment.is_high_availability:
            ip = self.environment.rabbit_mq_queue_ip
        else:
            ip = self.first_node_with_role("controller").ipaddress
        url = "{host}:15672".format(host=ip)

        return rabbit.Client(url, user="guest", passwd="guest")

    @property
    def horizon_ip(self):
        """Returns IP of Horizon."""
        try:
            return self.override_attrs['vips']['nova-api']
        except KeyError:
            return self.first_node_with_role("controller").ipaddress

    @property
    def features_dict(self):
        container = {}
        for feature in self.features:
            container.update(feature.to_dict)
        return container
