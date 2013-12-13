from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client
from cinderclient.v1 import client as cinder_client

from monster import util


class Creds(object):
    """
    Credentials to authenticate with OpenStack
    """
    def __init__(self, user=None, password=None, apikey=None, region=None,
                 auth_url=None, auth_system=None, provisioner="openstack"):
        self.user = user
        self.password = password
        self.apikey = apikey
        self.region = region
        self.system = auth_system
        self.auth_url = auth_url


class Clients(object):
    """
    Openstack client generator
    """
    def __init__(self, creds):
        self.creds = creds
        insecure = False
        cacert = None
        self.creds_dict = dict(
            username=self.creds.user,
            api_key=self.creds.apikey,
            password=self.creds.password,
            project_id=self.creds.user,
            region_name=self.creds.region,
            insecure=insecure,
            cacert=cacert,
            auth_url=self.creds.auth_url,
        )

    def novaclient(self):
        """
        Openstack novaclient generator
        """
        util.logger.debug(
            'novaclient connection created using token "%s" and url "%s"'
            % (self.creds_dict['username'], self.creds_dict['auth_url'])
        )
        self.creds_dict.update({
            'auth_system': self.creds.system
        })
        if self.creds_dict['password']:
            self.creds_dict.update({
                'api_key': self.creds.password})
            self.creds_dict.pop("password")

        client = nova_client.Client(**self.creds_dict)
        return client

    def cinderclient(self):
        """
        Openstack cinderclient generator
        """
        util.logger.debug(
            'cinderclient connection created using token "%s" and url "%s"'
            % (self.creds_dict['username'], self.creds_dict['auth_url'])
        )
        client = cinder_client.Client(**self.creds_dict)
        return client

    def neutronclient(self):
        """
        Openstack neutronclient generator
        """
        util.logger.debug(
            'neutron connection created using token "%s" and url "%s"'
            % (self.creds_dict['username'], self.creds_dict['auth_url'])
        )

        client = neutron_client(auth_url=self.creds_dict['auth_url'],
                                username=self.creds_dict['username'],
                                password=self.creds_dict['password'],
                                tenant_name=self.creds_dict['username'],
                                api_key=self.creds_dict['api_key'])
        return client

    def get_client(self, client):
        """
        Client generator
        :param client: desired client
        :type client: str
        """
        client_type = getattr(self, client)
        if client_type is None:
            raise Exception('No Client Type Found')
        else:
            return client_type()
