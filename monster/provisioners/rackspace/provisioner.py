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
        self.given_names = set()

        self.creds = openstack_client.Creds(
            username=rackspace['user'], apikey=rackspace['api_key'],
            auth_url=rackspace['auth_url'], region=rackspace['region'],
            auth_system=rackspace['plugin'])

        pyrax.set_setting("identity_type", "rackspace")
        pyrax.set_credentials(self.creds.username, api_key=self.creds.apikey,
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
            except:
                obj = self.neutron.create(
                    desired_network,
                    cidr=rackspace['network'][desired_network]['cidr']
                )
            networks.append({"net-id": obj.id})
        return networks

    def post_provision(self, node):
        """Tasks to be done after a Rackspace node is provisioned.
        :param node: Node object to be tasked
        :type node: Monster.Node
        """
        self.mkswap(node)
        self.update(node)
        if "centos" in node.os_name:
            self.rdo(node)
        if "controller" in node.name:
            self.hosts(node)

    def rdo(self, node):
        logger.info("Installing RDO kernel.")
        kernel = active.config['rcbops']['compute']['kernel']['centos']
        version = kernel['version']
        install = kernel['install']
        if version not in node.run_cmd("uname -r")['return']:
            node.run_cmd(install)
            node.run_cmd("reboot now")
            check_port(node.ipaddress, 22)

    @staticmethod
    def hosts(node):
        """
        remove /etc/hosts entries
        rabbitmq uses hostnames and don't listen on the existing public ifaces
        :param node: Node object to clean ifaces
        :type node: Monster.node
        """
        cmd = ("sed '/{0}/d' /etc/hosts > /etc/hosts; "
               "echo '127.0.0.1 localhost' >> /etc/hosts".format(node.name))
        node.run_cmd(cmd)

    @staticmethod
    def mkswap(node, size=2):
        """Makes a swap file of size on the node.
        :param node: Node to create swap file
        :type node: monster.Node
        :param size: Size of swap file in GBs
        :type size: int
        """
        logger.info("Making swap file on:{0} of {1}GBs".format(node.name,
                                                               size))
        size_b = 1048576 * size
        node.run_cmd(
            "dd if=/dev/zero of=/mnt/swap bs=1024 count={size_b}; "
            "mkswap /mnt/swap; "
            "sed 's/vm.swappiness.*$/vm.swappiness=25/g' /etc/sysctl.conf "
            "> /etc/sysctl.conf; "
            "sysctl vm.swappiness=30; "
            "swapon /mnt/swap; "
            "echo '/mnt/swap swap swap defaults 0 0' >> /etc/fstab"
            .format(size_b=size_b), attempts=5)

    @staticmethod
    def update(node):
        """
        Pulls updates from the repos
        :param node: Node to update
        :type node: monster.Node
        """
        logger.info("Updating node:{0}".format(node.name))
        cmds = ["DEBIAN_FRONTEND=noninteractive apt-get update -y",
                "DEBIAN_FRONTEND=noninteractive apt-get upgrade -y",
                "DEBIAN_FRONTEND=noninteractive apt-get install "
                "openssh-client git curl -y"]
        if node.os_name == "centos":
            cmds = ["yum update -y",
                    "yum upgrade -y",
                    "yum install openssh-clients git curl -y",
                    ("wget http://dl.fedoraproject.org/pub/epel/6/x86_64/"
                     "epel-release-6-8.noarch.rpm"),
                    ("wget http://rpms.famillecollet.com/enterprise/remi-"
                     "release-6.rpm"),
                    "sudo rpm -Uvh remi-release-6*.rpm epel-release-6*.rpm",
                    "/sbin/iptables -F",
                    "/etc/init.d/iptables save",
                    "/sbin/iptables -L"]
        node.run_cmd("; ".join(cmds))
