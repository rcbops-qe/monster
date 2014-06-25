import logging
import pyrax

import monster.active as active
import monster.provisioners.openstack.provisioner as openstack
import monster.clients.openstack as openstack_client
from monster.utils.access import check_port

logger = logging.getLogger(__name__)


class Provisioner(openstack.Provisioner):
    """Provisions Chef nodes in Rackspace Cloud Servers VMS."""
    def __init__(self):
        rackspace = active.config['secrets']['rackspace']
        self.creds = openstack_client.Creds(username=rackspace['user'],
                                            apikey=rackspace['api_key'],
                                            auth_url=rackspace['auth_url'],
                                            region=rackspace['region'],
                                            auth_system=rackspace['plugin'])

        pyrax.set_setting("identity_type", "rackspace")
        pyrax.set_credentials(username=self.creds.username,
                              api_key=self.creds.apikey,
                              region=self.creds.region_name)

        self.compute_client = pyrax.cloudservers
        self.neutron = pyrax.cloud_networks

    def __str__(self):
        return 'rackspace'

    def get_networks(self):
        rackspace = active.config[str(self)]
        desired_networks = rackspace['networks']
        networks = []
        for desired_network in desired_networks:
            try:
                obj = next(network for network in self.neutron.list()
                           if network.label == desired_network)
            except StopIteration:
                cidr = rackspace['network'][desired_network]['cidr']
                obj = self.neutron.create(desired_network, cidr=cidr)
            networks.append({"net-id": obj.id})
        return networks

    def post_provision(self, node):
        """Tasks to be done after a Rackspace node is provisioned.
        :param node: Node object to be tasked
        :type node: Monster.Node
        """
        node.mkswap(size=2)
        node.initial_update()
        if "centos" in node.os_name:
            self.rdo(node)
        if "controller" in node.name:
            self.hosts(node)

    def rdo(self, node):
        logger.info("Installing RDO kernel.")
        kernel = active.config['rcbops']['compute']['kernel']['centos']
        if kernel['version'] not in node.run_cmd("uname -r")['return']:
            node.run_cmd(kernel['install'] + "; reboot now")
            check_port(node.ipaddress, 22)

    def hosts(self, node):
        """Remove /etc/hosts entries; Rabbitmq uses hostnames and doesn't
        listen on the existing public ifaces.
        :param node: Node object to clean ifaces
        :type node: Monster.node
        """
        node.run_cmd("sed '/{0}/d' /etc/hosts > /etc/hosts; echo '127.0.0.1 "
                     "localhost' >> /etc/hosts" .format(node.name))
