"""
Module to test OpenStack deployments with CloudCafe
"""

import os

from monster import util
from monster.tests.test import Test
from monster.server_helper import run_cmd


class CloudCafe(Test):
    def __init__(self, deployment):
        super(CloudCafe, self).__init__(deployment)

    def test(self):
        raise NotImplementedError

    def get_endpoint(self):
        auth_url = "http://{0}:5000/v2.0".format(self.deployment.horizon_ip())
        return auth_url

    def get_admin_user(self):
        override = self.deployment.environment.override_attributes
        keystone = override['keystone']
        user = keystone['admin_user']
        users = keystone['users']
        password = users[user]['password']
        tenant = users[user]['roles']['admin'][0]
        return (user, password, tenant)

    def get_non_admin_user(self):
        override = self.deployment.environment.override_attributes
        keystone = override['keystone']
        users = keystone['users']
        non_admin_users = (user for user in users.keys()
                           if "admin" not in users[user]['roles'].keys())
        user = next(non_admin_users)
        password = users[user]['password']
        tenant = users[user]['roles']['Member'][0]
        return (user, password, tenant)

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
        return (image_id1, image_id2)

    def get_admin_ids(self):
        return ("blah", "blah", "blah")

    def export_variable(self, section, variable, value):
        export = "CAFE_{0}_{1}".format(section, variable)
        os.environ[export] = value

    def config(self, network_name=None, files=None):
        endpoint = self.get_endpoint()
        admin_user, admin_password, admin_tenant = self.get_admin_user()
        admin_tenant_id, admin_user_id, admin_project_id = self.get_admin_ids()
        second_user, second_password, second_tenant = self.get_non_admin_user()
        primary_image_id, secondary_image_id = self.get_image_ids()

        args = {
            "endpoint": endpoint,
            "admin_user": admin_user,
            "admin_password": admin_password,
            "admin_tenant": admin_tenant,
            "admin_tenant_id": admin_tenant_id,
            "admin_user_id": admin_user_id,
            "admin_project_id": admin_project_id,
            "second_user": second_user,
            "second_password": second_password,
            "second_tenant": second_tenant,
            "primary_image_id": primary_image_id,
            "secondary_image_id": secondary_image_id,
            "network_name": network_name}

        util.template_file("files/cloudcafe.core.config",
                           destination="dest", args=args)
