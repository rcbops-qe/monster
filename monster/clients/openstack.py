import logging

from novaclient.v1_1 import client as nova_client
from neutronclient.v2_0.client import Client as neutron_client
from cinderclient.v1 import client as cinder_client
from keystoneclient.v2_0 import client as keystone_client

logger = logging.getLogger(__name__)


class Creds(object):
    """Credentials to authenticate with OpenStack."""
    def __init__(self, username=None, password=None, apikey=None,
                 region=None, auth_url=None, auth_system="keystone",
                 tenant_name=None, project_id=None, insecure=False,
                 cacert=None):
        self.username = username
        self.tenant_name = tenant_name
        self.api_key = apikey
        self.apikey = apikey
        self.password = password
        self.project_id = project_id
        self.region_name = region
        self.insecure = insecure
        self.cacert = cacert
        self.auth_url = auth_url


class Clients(object):
    """Openstack client generator."""
    def __init__(self, creds):
        self.creds = creds.__dict__
        if not self.creds["tenant_name"]:
            self.creds["tenant_name"] = self.creds["username"]

    @property
    def keystoneclient(self):
        """Openstack keystone client."""

        logger.debug(
            "keystone connection created using token {0} and url {1}".format(
                self.creds['username'], self.creds['auth_url']))
        args = ["username", "password", "tenant_name", "auth_url"]
        return keystone_client.Client(**self.build_args(args))

    @property
    def novaclient(self):
        """Openstack novaclient generator."""
        logger.debug(
            'novaclient connection created using token "%s" and url "%s"'
            % (self.creds['username'], self.creds['auth_url'])
        )
        args = ["username", ("api_key", "password"), "project_id", "auth_url"]
        client = nova_client.Client(**self.build_args(args))
        return client

    @property
    def cinderclient(self):
        """Openstack cinderclient generator."""
        logger.debug(
            'cinderclient connection created using token "%s" and url "%s"'
            % (self.creds['username'], self.creds['auth_url'])
        )
        args = ["username", ("api_key", "password"), "project_id", "auth_url"]
        return cinder_client.Client(**self.build_args(args))

    @property
    def neutronclient(self):
        """Openstack neutronclient generator."""
        logger.debug(
            'neutron connection created using token "%s" and url "%s"'
            % (self.creds['username'], self.creds['auth_url'])
        )

        args = ["auth_url", "username", "password", "tenant_name"]
        return neutron_client(**self.build_args(args))

    def get_client(self, client):
        """Client generator.
        :param client: desired client
        :type client: str
        """
        client_type = getattr(self, client)
        if client_type is None:
            raise Exception('No Client Type Found')
        else:
            return client_type()

    def add_cred(self, args, to_key, from_key=None):
        if not from_key:
            from_key = to_key
        value = self.creds[from_key]
        if value:
            args[to_key] = value
            return True
        return False

    def build_args(self, req_args):
        args = {}
        for arg in req_args:
            if isinstance(arg, basestring):
                self.add_cred(args, arg, arg)
            else:
                self.add_cred(args, arg[0], arg[1])
        return args
