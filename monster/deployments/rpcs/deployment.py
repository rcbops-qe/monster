import os
import sys
import webbrowser

import chef
import pyrabbit.api as rabbit

import monster.active as active
import monster.upgrades.util as upgrades_util
import monster.clients.openstack as openstack
import monster.deployments.base as base
import monster.nodes.chef_.node as monster_chef

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
        self.provisioner.build_nodes(self)

    def __str__(self):
        return str(self.to_dict)

    def build(self):
        """Saves deployment for restore after build."""

        super(Deployment, self).build()
        self.save_to_environment()

    def save_to_environment(self):
        """Save deployment restore attributes to chef environment."""
        deployment = self.to_dict
        self.environment.add_override_attr('deployment', deployment)

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

    def update_environment(self):
        """Saves deployment for restore after update environment."""

        super(Deployment, self).update_environment()
        self.save_to_environment()
        with open("{0}.json".format(self.name), "w") as f:
            f.write(str(self.environment))

    def destroy(self):
        """Destroys Chef Deployment."""

        self.status = "destroying"
        super(Deployment, self).destroy()
        # Destroy rogue nodes
        if not self.nodes:
            pass
            # destroy rouge nodes
        self.environment.destroy()
        self.status = "destroyed"

    def horizon(self):
        url = "https://{0}".format(self.horizon_ip)
        webbrowser.open_new_tab(url)

    def openrc(self):
        """Opens a new shell with variables loaded for nova-client."""

        user_name = self.override_attrs['keystone']['admin_user']
        user = self.override_attrs['keystone']['users'][user_name]
        password = user['password']
        tenant = user['roles'].keys()[0]
        controller = next(self.search_role('controller'))
        chef_node = chef.Node(controller.name, self.environment.local_api)
        url = chef_node.normal['keystone']['publicURL']
        strategy = 'keystone'
        openrc = {'OS_USERNAME': user_name, 'OS_PASSWORD': password,
                  'OS_TENANT_NAME': tenant, 'OS_AUTH_URL': url,
                  'OS_AUTH_STRATEGY': strategy, 'OS_NO_CACHE': '1'}
        for key in openrc.keys():
            os.putenv(key, openrc[key])
        os.system(os.environ['SHELL'])

    @property
    def to_dict(self):
        features = {key: value for (key, value) in
                    ((str(x).lower(), x.rpcs_feature) for x in self.features)}
        nodes = [n.name for n in self.nodes]
        return {'nodes': nodes, 'features': features,
                'name': self.name, 'os_name': self.os_name,
                'branch': self.branch, 'status': self.status,
                'product': self.product, 'provisioner': self.provisioner_name}

    @property
    def openstack_clients(self):
        """Setup OpenStack clients generator for deployment."""
        keystone = self.override_attrs['keystone']
        users = keystone['users']
        user = keystone['admin_user']
        region = "RegionOne"
        password = users[user]["password"]
        tenant_name = "admin"
        auth_url = "http://{0}:5000/v2.0".format(self.horizon_ip())

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
            controller = next(self.search_role("controller"))
            ip = controller.ipaddress
        url = "{ip}:15672".format(ip=ip)

        user = "guest"
        password = "guest"

        return rabbit.Client(url, user, password)

    @property
    def horizon_ip(self):
        """Returns IP of Horizon.
        :rtype: str
        """
        controller = next(self.search_role('controller'))
        ip = controller.ipaddress
        if "vips" in self.override_attrs:
            ip = self.override_attrs['vips']['nova-api']
        return ip

    def wrap_node(self, node):
        remote_api = self.environment.remote_api
        if remote_api:
            remote_node = chef.Node(node.name, remote_api)
            if remote_node.exists:
                node = remote_node
        ip = node['ipaddress']
        user = node['current_user']
        default_pass = active.config['secrets']['default_pass']
        password = node.get('password', default_pass)
        name = node.name
        archive = node.get('archive', {})
        run_list = node.run_list

        chef_remote_node = monster_chef.Node(name=name, ip=ip,
                                             user=user, password=password,
                                             deployment=self,
                                             run_list=run_list)

        chef_remote_node.add_features(archive.get('features', []))
        return chef_remote_node
