from functools import partial
import logging
import os
import webbrowser

import pyrabbit.api as rabbit

import monster.active as active
import monster.threading_iface as threading
import monster.clients.openstack as openstack
import monster.deployments.base as base
import monster.upgrades.util as upgrades_util

logger = logging.getLogger(__name__)


class Deployment(base.Deployment):
    """Deployment mechanisms specific to a RPCS deployment using Chef as
    configuration management.
    """
    def __init__(self, name, clients=None):
        """Initializes a RPCS deployment object."""
        super(Deployment, self).__init__(name=name, status="provisioning",
                                         clients=clients)
        self.has_controller = False
        self.has_orch_master = False
        self.nodes = self.acquire_nodes(active.template['nodes'])

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

    def acquire_nodes(self, specs):
        active.node_names = set(self.node_names)
        func_list = [partial(self.provisioner.build_node, self, spec)
                     for spec in specs]
        nodes = threading.execute(func_list)
        assert nodes is not None
        nodes.sort(key=lambda node: node.name)
        return nodes

    def add_nodes(self, node_request):
        logger.info("Adding nodes...")
        additional_nodes = self.acquire_nodes(node_request)
        self.nodes.extend(additional_nodes)
        self.nodes.sort(key=lambda node: node.name)
        chefserver = self.first_node_with_role('chefserver')
        chefserver.feature('chefserver').remote_other_nodes()
        threading.execute(node.build for node in additional_nodes)
        self.update()

    def build_nodes(self):
        base.logger.info("Building chef nodes...")
        for node in self.chefservers:
            node.build()
        super(Deployment, self).build_nodes()

    def update(self):
        super(Deployment, self).update()
        for node in self.nodes_without_role('chefserver'):
            node.run_cmd('chef-client')

    def upgrade(self, branch_name):
        """Upgrades the deployment."""
        rc = "rc" in branch_name
        upgrade = upgrades_util.get_upgrade(self, branch_name)
        upgrade.upgrade(rc)

    def destroy(self):
        """Destroys Chef Deployment."""
        self.status = "destroying"
        super(Deployment, self).destroy()
        self.environment.destroy()
        self.status = "destroyed"

    def update_environment(self):
        """Saves deployment for restore after update environment."""
        super(Deployment, self).update_environment()
        self.save_to_environment()

    def save_to_environment(self):
        """Save deployment restore attributes to chef environment."""
        deployment = self.to_dict
        self.environment.add_override_attr('deployment', deployment)

    def horizon(self):
        url = "https://{ip}".format(ip=self.horizon_ip)
        webbrowser.open_new_tab(url)

    def openrc(self):
        """Opens a new shell with variables loaded for nova-client."""
        strategy = 'keystone'
        keystone = self.override_attrs['keystone']
        url = self.controller(1).local_node['keystone']['publicURL']
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
            ip = self.controller(1).ipaddress
        url = "{host}:15672".format(host=ip)

        return rabbit.Client(url, user="guest", passwd="guest")

    @property
    def horizon_ip(self):
        """Returns IP of Horizon."""
        try:
            return self.override_attrs['vips']['nova-api']
        except KeyError:
            return self.controller(1).ipaddress

    @property
    def features_dict(self):
        container = {}
        for feature in self.features:
            container.update(feature.to_dict)
        return container

    @property
    def chefservers(self):
        return self.nodes_with_role('chefserver')
