"""
Module to test OpenStack deployments with CloudCafe
"""

import os

from monster.tests.test import Test
from monster.utils.access import run_cmd


class CloudCafe(Test):
    def __init__(self, deployment):
        super(CloudCafe, self).__init__(deployment)

    def get_endpoint(self):
        auth_url = "http://{0}:5000".format(self.deployment.horizon_ip())
        return auth_url

    def get_admin_user(self):
        keystone = self.deployment.override_attrs['keystone']
        user = keystone['admin_user']
        users = keystone['users']
        password = users[user]['password']
        tenant = users[user]['roles']['admin'][0]
        return user, password, tenant

    def get_non_admin_user(self):
        override = self.deployment.override_attrs
        keystone = override['keystone']
        users = keystone['users']
        non_admin_users = (user for user in users.keys()
                           if "admin" not in users[user]['roles'].keys())
        user = next(non_admin_users)
        password = users[user]['password']
        tenant = users[user]['roles']['Member'][0]
        return user, password, tenant

    def get_image_ids(self):
        nova = self.deployment.openstack_clients.novaclient
        image_ids = (i.id for i in nova.images.list())
        try:
            image_id1 = next(image_ids)
        except StopIteration:
            # No images
            exit(1)
        try:
            image_id2 = next(image_ids)
        except StopIteration:
            # Only one image
            image_id2 = image_id1
        return image_id1, image_id2

    def get_admin_ids(self, user, tenant, project):
        keystone = self.deployment.openstack_clients.keystoneclient
        user_id = keystone.user_id
        tenant_id = keystone.tenant_id
        project_id = keystone.project_id
        return tenant_id, user_id, project_id

    def get_network_id(self, network_name):
        neutron = self.deployment.openstack_clients.neutronclient
        return next(net['id'] for net in neutron.list_networks()['networks'] if
                    net['name'] == network_name)

    def export_variables(self, section, values):
        for variable, value in values.items():
            export = "CAFE_{0}_{1}".format(section, variable)
            os.environ[export] = value

    def config(self, cmd, network_name="ENV01-FLAT", files=None):
        endpoint = self.get_endpoint()
        admin_user, admin_password, admin_tenant = self.get_admin_user()
        admin_tenant_id, admin_user_id, admin_project_id = self.get_admin_ids(
            admin_user, admin_password, admin_tenant)
        second_user, second_password, second_tenant = self.get_non_admin_user()
        primary_image_id, secondary_image_id = self.get_image_ids()
        if self.deployment.has_feature("neutron"):
            network_id = self.get_network_id(network_name)
            networks = "{'%s':{'v4': True, 'v6': False}}" % network_name
        else:
            # How connectivity works in cloudcafe for novanet needs work
            # May not be possible atm due to floating ips
            network_name = "public"
            network_id = "0000" * 5
            networks = "{'%s':{'v4': True, 'v6': False}}" % network_name

        endpoint_versioned = "{0}/v2.0".format(endpoint)
        admin_endpoint_versioned = endpoint_versioned.replace("5000", "35357")

        args = {
            "compute_admin_user": {
                "username": admin_user,
                "password": admin_password,
                "tenant_name": admin_tenant
            },
            "user_auth_config": {
                "endpoint": endpoint
            },
            "coumpute_admin_auth_config": {
                "endpoint": endpoint
            },
            "user": {
                "username": admin_user,
                "password": admin_password,
                "tenant_name": admin_tenant,
                "tenant_id": admin_tenant_id,
                "user_id": admin_user_id,
                "project_id": admin_project_id
            },
            "compute_secondary_user": {
                "username": second_user,
                "password": second_password,
                "tenant_name": second_tenant
            },
            "images": {
                "primary_image": primary_image_id,
                "secondary_image": secondary_image_id
            },
            "servers": {
                "network_for_ssh": network_name,
                "expected_networks": networks,
                "default_network": network_id
            },
            "identity_v2_user": {
                "username": second_user,
                "password": second_password,
                "tenant_name": second_tenant,
                "authentication_endpoint": endpoint_versioned
            },
            "identity_v2_admin": {
                "username": admin_user,
                "password": admin_password,
                "tenant_name": admin_tenant,
                "authentication_endpoint": admin_endpoint_versioned
            }
        }

        for section, values in args.items():
            self.export_variables(section, values)

        run_cmd(cmd)
