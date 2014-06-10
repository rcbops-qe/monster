import logging
import thread
import time

import monster.nodes.chef_.node as monster_chef
import monster.active as active
import monster.provisioners.base as base
import monster.clients.openstack as openstack
from monster.utils.access import check_port

logger = logging.getLogger(__name__)


class Provisioner(base.Provisioner):
    """Provisions Chef nodes in OpenStack VMS."""
    def __init__(self):
        self.given_names = set()
        self.creds = openstack.Creds()

        openstack_clients = openstack.Clients(self.creds)
        self.auth_client = openstack_clients.keystoneclient
        self.compute_client = openstack_clients.novaclient

    def __str__(self):
        return 'openstack'

    def name(self, name, deployment):
        """Helper for naming nodes.
        :param name: name for node
        :type name: str
        :param deployment: deployment object
        :type deployment: monster.deployments.base.Deployment
        :rtype: str
        """
        root = "{0}-{1}".format(deployment.name, name)
        if root not in active.node_names:
            active.node_names.add(root)
            return root
        else:
            counter = 2
            name = root
            while name in active.node_names:
                name = "{prefix}{suffix}".format(prefix=root,
                                                 suffix=counter)
                counter += 1
            active.node_names.add(name)
            return name

    def provision_node(self, deployment, specs):
        """Provisions a chef node using OpenStack.
        :param deployment: ChefDeployment to provision for
        :type deployment: monster.deployments.base.Deployment
        :rtype: list
        """
        logger.info("Provisioning in the cloud!")
        node_role = specs[0]
        node_name = self.name(node_role, deployment)

        flavor_name = active.config['rackspace']['roles'][node_role]
        flavor = self.get_flavor(flavor_name).id
        image = self.get_image(deployment.os_name).id
        networks = self.get_networks()

        logger.info("Building: {node}".format(node=node_name))
        server, password = self.get_server(node_name, image, flavor,
                                           nics=networks)

        return monster_chef.Node(node_name, ip=server.accessIPv4, user="root",
                                 password=password, uuid=server.id,
                                 deployment=deployment, features=specs)

    def get_server(self, node_name, image, flavor, nics):
        for creation_attempt in range(3):
            server = self.compute_client.servers.create(node_name, image,
                                                        flavor, nics=nics)
            password = server.adminPass
            for wait_for_state in range(100):
                server = self.compute_client.servers.get(server.id)
                if server.status == "ACTIVE":
                    check_port(server.accessIPv4, 22, timeout=2)
                    return server, password
                logger.info("{}: {}%".format(server.status, server.progress))
                time.sleep(3)
            else:
                logger.error("Unable to build instance. Retrying...")
                server.delete()
        else:
            logger.exception("Server creation failed three times; exiting...")

    def destroy_node(self, node):
        """Destroys Chef node from OpenStack.
        :param node: node to destroy
        :type node: monster.nodes.base.Node
        """
        self.compute_client.servers.get(node.uuid).delete()

    def get_flavor(self, flavor):
        desired_flavor = active.config[str(self)]['flavors'][flavor]
        return next(flavor for flavor in self.compute_client.flavors.list()
                    if flavor.name == desired_flavor)

    def get_image(self, image):
        desired_image = active.config[str(self)]['images'][image]
        return next(image for image in self.compute_client.images.list()
                    if image.name == desired_image)

    def get_networks(self):
        desired_networks = active.config[str(self)]['networks']
        return [{"net-id": network.id} for network in self.neutron.list()
                if network in desired_networks]

    def power_down(self, node):
        node.run_cmd("echo 1 > /proc/sys/kernel/sysrq; "
                     "echo o > /proc/sysrq-trigger")

    def power_up(self, node):
        server = self.compute_client.servers.get(node.uuid)
        server.reboot("hard")
