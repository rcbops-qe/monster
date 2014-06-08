import logging
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
        self.given_names = None
        self.creds = openstack.Creds()

        openstack_clients = openstack.Clients(self.creds)
        self.auth_client = openstack_clients.keystoneclient
        self.compute_client = openstack_clients.novaclient

    def __str__(self):
        return 'openstack'

    def name(self, name, deployment):
        """Helper for naming nodes.
        :param name: name for node
        :type name: String
        :param deployment: deployment object
        :type deployment: monster.deployments.base.Deployment
        :rtype: string
        """
        self.given_names = self.given_names or deployment.node_names

        root = "{0}-{1}".format(deployment.name, name)
        if root not in self.given_names:
            self.given_names.append(root)
            return root
        else:
            counter = 2
            name = root
            while name in self.given_names:
                name = "{prefix}{suffix}".format(prefix=root, suffix=counter)
                counter += 1
            self.given_names.append(name)
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

        server = self.compute_client.servers.create(node_name, image, flavor,
                                                    nics=networks)

        while "ACTIVE" not in server.status:
            server = self.wait_for_state(self.compute_client.servers.get,
                                         server, "status",
                                         ["ACTIVE", "ERROR"],
                                         interval=15, attempts=10)

            if "ACTIVE" not in server.status:
                logger.error("Unable to build instance. Retrying...")
                server.delete()

        check_port(server.accessIPv4, 22, timeout=2)

        return monster_chef.Node(node_name, ip=server.accessIPv4, user="root",
                                 password=server.adminPass, uuid=server.id,
                                 deployment=deployment)


    def destroy_node(self, node):
        """Destroys Chef node from OpenStack.
        :param node: node to destroy
        :type node: monster.nodes.base.Node
        """
        self.compute_client.servers.get(node.uuid).delete()

    def get_flavor(self, flavor):
        try:
            flavor_name = active.config[str(self)]['flavors'][flavor]
        except KeyError:
            raise Exception("Flavor not supported: {}".format(flavor))
        return self._client_search(self.compute_client.flavors.list,
                                   "name", flavor_name, attempts=10)

    def get_image(self, image):
        try:
            image_name = active.config[str(self)]['images'][image]
        except KeyError:
            raise Exception("Image not supported: {}".format(image))
        return self._client_search(self.compute_client.images.list, "name",
                                   image_name, attempts=10)

    def get_networks(self):
        desired_networks = active.config[str(self)]['networks']
        networks = []
        for network in desired_networks:
            obj = self._client_search(self.neutron.list, "label",
                                      network, attempts=10)
            networks.append({"net-id": obj.id})
        return networks

    @staticmethod
    def _client_search(collection_fun, attr, desired, attempts=None):
        """Searches for a desired attribute in a list of objects.
        :param collection_fun: function to get list of objects
        :type collection_fun: function
        :param attr: attribute of object to check
        :type attr: string
        :param desired: desired value of object's attribute
        :type desired: object
        :param attempts: number of attempts to achieve state
        :type attempts: int
        :rtype: object
        """
        obj_collection = None
        for attempt in range(attempts):
            try:
                obj_collection = collection_fun()
                break
            except Exception as e:
                logger.error("Wait: Request error:{0}-{1}".format(desired, e))
                continue
        get_attr = lambda x: getattr(x, attr)
        logger.debug("Search:{0} for {1} in {2}".format(
            attr, desired, ",".join(map(get_attr, obj_collection))))
        for obj in obj_collection:
            if getattr(obj, attr) == desired:
                return obj
        raise Exception("Client search fail: {} not found".format(desired))

    ##TODO: rewrite this - i don't think it's doing what we want (jcourtois)
    @staticmethod
    def wait_for_state(fun, obj, attr, desired, interval=10,
                       attempts=18):
        """Waits for a desired state of an object.
        :param fun: function to update object
        :type fun: function
        :param obj: object which to check state
        :type obj: obj
        :param attr: attribute of object of which state resides
        :type attr: str
        :param desired: desired states of attribute
        :type desired: list of str
        :param interval: interval to check state in secs
        :param interval: int
        :param attempts: number of attempts to achieve state
        :type attempts: int
        :rtype: obj
        """
        for attempt in range(attempts):
            from IPython import embed; embed()
            logger.debug("Attempt: {0}/{1}".format(attempt+1, attempts))
            state = getattr(obj, attr)
            logger.info("Waiting: {0}, {1}: {2}".format(obj, attr, state))
            if state in desired or state==desired:
                break
            time.sleep(interval)
            obj = fun(obj.id)
        return obj

    def power_down(self, node):
        node.run_cmd("echo 1 > /proc/sys/kernel/sysrq; "
                     "echo o > /proc/sysrq-trigger")

    def power_up(self, node):
        server = self.compute_client.servers.get(node.uuid)
        server.reboot("hard")
