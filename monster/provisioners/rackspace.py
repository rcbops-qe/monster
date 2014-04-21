import logging
import pyrax

from monster import util
from openstack import Openstack
from monster.clients.openstack import Creds
from monster.server_helper import check_port

logger = logging.getLogger(__name__)


class Rackspace(Openstack):
    """
    Provisions chef nodes in Rackspace Cloud Servers vms
    """

    def __init__(self):
        rackspace = util.config['secrets']['rackspace']

        self.names = []
        self.name_index = {}
        self.creds = Creds(
            username=rackspace['user'], apikey=rackspace['api_key'],
            auth_url=rackspace['auth_url'], region=rackspace['region'],
            auth_system=rackspace['plugin'])

        pyrax.set_setting("identity_type", "rackspace")
        pyrax.set_credentials(self.creds.username, api_key=self.creds.apikey,
                              region=self.creds.region_name)

        self.compute_client = pyrax.cloudservers
        self.neutron = pyrax.cloud_networks

    def get_networks(self):
        rackspace = util.config[str(self)]
        desired_networks = rackspace['networks']
        networks = []
        for network in desired_networks:
            try:
                obj = self._client_search(self.neutron.list, "label",
                                          network, attempts=10)
            except:
                obj = self.neutron.create(
                    network,
                    cidr=rackspace['network'][network]['cidr']
                )
            networks.append({"net-id": obj.id})
        return networks

    def post_provision(self, node):
        """
        Tasks to be done after a rackspace node is provisioned
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
        kernel = util.config['rcbops']['compute']['kernel']['centos']
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
        """
        Makes a swap file of size on the node
        :param node: Node to create swap file
        :type node: monster.Node
        :param size: Size of swap file in GBs
        :type size: int
        """
        logger.info("Making swap file on:{0} of {1}GBs".format(node.name,
                                                               size))
        size_b = 1048576 * size
        cmds = [
            "dd if=/dev/zero of=/mnt/swap bs=1024 count={0}".format(size_b),
            "mkswap /mnt/swap",
            "sed 's/vm.swappiness.*$/vm.swappiness=25/g' "
            "/etc/sysctl.conf > /etc/sysctl.conf",
            "sysctl vm.swappiness=30",
            "swapon /mnt/swap",
            "echo '/mnt/swap swap swap defaults 0 0' >> /etc/fstab"]
        node.run_cmd("; ".join(cmds))

    @staticmethod
    def update(node):
        """
        Pulls updates from the repos
        :param node: Node to update
        :type node: monster.Node
        """
        logger.info("Updating node:{0}".format(node.name))
        cmds = ["apt-get update -y",
                "apt-get upgrade -y",
                "apt-get install openssh-client git curl -y"]
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
        node.run_cmd(";".join(cmds))
