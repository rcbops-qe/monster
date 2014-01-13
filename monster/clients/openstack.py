from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client
from cinderclient.v1 import client as cinder_client
from keystoneclient.v2_0 import client as keystone_client

from monster import util


class Creds(dict):
    """
    Credentials to authenticate with OpenStack
    """
    def __init__(self, username=None, password=None, apikey=None,
                 region=None, auth_url=None, auth_system=None,
                 tenant_name=None, project_id=None, insecure=False,
                 cacert=None):
        self.username = username
        self.tenant_name = tenant_name
        self.apikey = apikey
        self.password = password
        self.project_id = project_id
        self.region_name = region
        self.insecure = insecure
        self.cacert = cacert
        self.auth_url = auth_url


class Clients(object):
    """
    Openstack client generator
    """
    def __init__(self, creds):
        self.creds = creds.__dict__

    def keystoneclient(self):
        """
        Openstack keystone client
        """

        util.logger.debug(
            "keystone connection created using token {0} and url {1}".format(
                self.creds['username'], self.creds['auth_url']))

        return keystone_client.Client(**self.creds)

    def novaclient(self):
        """
        Openstack novaclient generator
        """
        util.logger.debug(
            'novaclient connection created using token "%s" and url "%s"'
            % (self.creds['username'], self.creds['auth_url'])
        )
        self.creds.update({
            'auth_system': self.creds.system
        })

        key = None
        if 'password' in self.creds:
            key = self.creds['password']
        else:
            key = self.creds['api_key']

        client = nova_client.Client(self.creds['username'], key,
                                    self.creds['username'],
                                    auth_url=self.creds['auth_url'])
        return client

    def cinderclient(self):
        """
        Openstack cinderclient generator
        """
        util.logger.debug(
            'cinderclient connection created using token "%s" and url "%s"'
            % (self.creds['username'], self.creds['auth_url'])
        )
        client = cinder_client.Client(**self.creds)
        return client

    def neutronclient(self):
        """
        Openstack neutronclient generator
        """
        util.logger.debug(
            'neutron connection created using token "%s" and url "%s"'
            % (self.creds['username'], self.creds['auth_url'])
        )

        client = neutron_client(auth_url=self.creds['auth_url'],
                                username=self.creds['username'],
                                password=self.creds['password'],
                                tenant_name=self.creds['username'],
                                api_key=self.creds['api_key'])
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
