import logging
import gevent

import monster.nodes.chef_.node as monster_chef
import monster.active as active
import monster.provisioners.base as base
import monster.clients.openstack as openstack
from monster.utils.access import run_cmd, check_port

logger = logging.getLogger(__name__)


class Provisioner(base.Provisioner):
    """Provisions Chef nodes in OpenStack VMS."""
    def __init__(self):
        self.given_names = []
        self.creds = openstack.Creds()

        openstack_clients = openstack.Clients(self.creds)
        self.auth_client = openstack_clients.keystoneclient
        self.compute_client = openstack_clients.novaclient

    def __str__(self):
        return 'openstack'

    def name(self, name, deployment, number=None):
        """Helper for naming nodes.
        :param name: name for node
        :type name: String
        :param deployment: deployment object
        :type deployment: monster.deployments.base.Deployment
        :param number: number to append to name
        :type number: int
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

        name = self.name(specs[0], deployment)
        flavor = active.config['rackspace']['roles'][specs[0]]

        server = self.build_instance(deployment, name, flavor)

        return monster_chef.Node(name, ip=server.accessIPv4, user="root",
                                 password=server.adminPass, uuid=server.id,
                                 deployment=deployment)


    def build_instance(self, name="server", image="ubuntu", flavor="2GBP"):
        """Builds an instance with desired specs.
        :param name: name of server
        :type name: string
        :param image: desired image for server
        :type image: string
        :param flavor: desired flavor for server
        :type flavor: string
        """
        # gather attributes
        flavor = self.get_flavor(flavor).id
        image = self.get_image(image).id
        networks = self.get_networks()

        # build instance
        logger.info("Building: {0}".format(name))
        server = self.compute_client.servers.create(name, image, flavor,
                                                    nics=networks)

        server = self.wait_for_state(self.compute_client.servers.get, server,
                                     "status", ["ACTIVE", "ERROR"],
                                     interval=15, attempts=10)
        if "ACTIVE" not in server.status:
            logger.error("Unable to build instance. Retrying...")
            server.delete()
            return self.build_instance(name=name, image=image, flavor=flavor)

        check_port(server.accessIPv4, 22, timeout=2)
        return server

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
            raise Exception("Flavor not supported:{0}".format(flavor))
        return self._client_search(self.compute_client.flavors.list,
                                   "name", flavor_name, attempts=10)

    def get_image(self, image):
        try:
            image_name = active.config[str(self)]['images'][image]
        except KeyError:
            raise Exception("Image not supported:{0}".format(image))
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
        raise Exception("Client search fail:{0} not found".format(desired))

    ##TODO: rewrite this - i don't think it's doing what we want (jcourtois)
    @staticmethod
    def wait_for_state(fun, obj, attr, desired, interval=30,
                       attempts=None):
        """Waits for a desired state of an object using gevent sleep.
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
            logger.debug("Attempt: {0}/{1}".format(attempt+1, attempts))
            logger.info("Waiting: {0}, {1}: {2}".format(obj, attr,
                                                        getattr(obj, attr)))
            gevent.sleep(interval)
            obj = fun(obj.id)
        return obj

    def power_down(self, node):
        node.run_cmd("echo 1 > /proc/sys/kernel/sysrq; "
                     "echo o > /proc/sysrq-trigger")

    def power_up(self, node):
        uuid = node['uuid']
        server = self.compute_client.servers.get(uuid)
        server.reboot("hard")
