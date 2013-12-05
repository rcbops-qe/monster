import logging

from novaclient.v1_1 import client as nova_client
from cinderclient.v1 import client as cinder_client

from monster import util


LOG = logging.getLogger(__name__)


class rax_plugin(object):
    def __init__(self):
        """Craetes an authentication plugin for use with Rackspace."""

        self.auth_url = self.global_auth()

    def global_auth(self):
        """Return the Rackspace Cloud US Auth URL."""

        return "https://identity.api.rackspacecloud.com/v2.0/"

    def _authenticate(self, cls, auth_url):
        """Authenticate against the Rackspace auth service."""

        body = {"auth": {
            "RAX-KSKEY:apiKeyCredentials": {
                "username": cls.user,
                "apiKey": cls.password,
                "tenantName": cls.projectid}}}
        return cls._authenticate(auth_url, body)

    def authenticate(self, cls, auth_url):
        """Authenticate against the Rackspace US auth service."""

        return self._authenticate(cls, auth_url)


class rax_creds(object):
    """
    Credentials to authenticate with Rackspace
    """
    def __init__(self):
        config = util.config['secrets']['rackspace']
        self.user = config['user']
        self.apikey = config['api_key']
        self.region = config['region']
        self.system = 'rackspace'
        self.plugin = rax_plugin()


class creds(object):
    """
    Credentials to authenticate with OpenStack
    """
    def __init__(self, user, apikey, region, auth_system):
        config = util.config['secrets']['openstack']
        self.user = user or config['user']
        self.apikey = apikey or config['api_key']
        self.region = region or config['region']
        self.system = auth_system or 'keystone'


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
            project_id=self.creds.user,
            region_name=self.creds.region,
            insecure=insecure,
            cacert=cacert,
            auth_url=self.creds.plugin.auth_url,
        )

    def novaclient(self):
        """
        Openstack novaclient generator
        """
        LOG.debug(
            'novaclient connection created using token "%s" and url "%s"'
            % (self.creds_dict['username'], self.creds_dict['auth_url'])
        )
        self.creds_dict.update({
            'auth_system': self.creds.system,
            'auth_plugin': self.creds.plugin
        })
        client = nova_client.Client(**self.creds_dict)
        return client

    def cinderclient(self):
        """
        Openstack cinderclient generator
        """
        LOG.debug(
            'cinderclient connection created using token "%s" and url "%s"'
            % (self.creds_dict['username'], self.creds_dict['auth_url'])
        )
        client = cinder_client.Client(**self.creds_dict)
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
