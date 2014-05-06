import logging
import gevent

import chef

import monster.provisioners.base as base
import monster.clients.openstack as openstack
import monster.active as active
from monster.utils.access import run_cmd, check_port

logger = logging.getLogger(__name__)


class Provisioner(base.Provisioner):
    """Provisions Chef nodes in OpenStack VMS."""
    def __init__(self):
        self.names = []
        self.name_index = {}
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
        if name in self.name_index:
            # Name already exists, use index to name
            num = self.name_index[name] + 1
            self.name_index[name] = num
            return "{0}-{1}{2}".format(deployment.name, name, num)

        # Name doesn't exist initialize index use name
        self.name_index[name] = 1
        return "{0}-{1}".format(deployment.name, name)

    def provision(self, deployment):
        """Provisions a chef node using OpenStack.
        :param deployment: ChefDeployment to provision for
        :type deployment: monster.deployments.base.Deployment
        :rtype: list
        """
        logger.info("Provisioning in the cloud!")
        # acquire connection

        # create instances concurrently
        events = []
        for features in active.template['nodes']:
            name = self.name(features[0], deployment)
            self.names.append(name)
            flavor = active.config['rackspace']['roles'][features[0]]
            events.append(gevent.spawn(self.chef_instance, deployment, name,
                                       flavor=flavor))
        gevent.joinall(events)

        # acquire chef nodes
        self.nodes += [event.value for event in events]
        return self.nodes

    def destroy_node(self, node):
        """Destroys Chef node from OpenStack.
        :param node: node to destroy
        :type node: monster.nodes.base.Node
        """
        client = node.client
        node = node.local_node
        if node.exists:
            self.compute_client.servers.get(node['uuid']).delete()
            node.delete()
        if client.exists:
            client.delete()

    def chef_instance(self, deployment, name, flavor="2GBP"):
        """Builds an instance with desired specs and initializes it with Chef.
        :param deployment: deployment to add to
        :type deployment: monster.deployments.base.Deployment
        :param name: name for instance
        :type name: string
        :param flavor: desired flavor for node
        :type flavor: string
        :rtype: chef.Node
        """
        image = deployment.os_name
        server, password = self.build_instance(name=name, image=image,
                                               flavor=flavor)
        run_list = ""
        if active.config[str(self)]['run_list']:
            run_list = ",".join(active.config[str(self)]['run_list'])
        run_list_arg = ""
        if run_list:
            run_list_arg = "-r {0}".format(run_list)
        client_version = active.config['chef']['client']['version']
        command = ("knife bootstrap {0} -u root -P {1} -N {2} {3}"
                   " --bootstrap-version {4}".format(server.accessIPv4,
                                                     password,
                                                     name,
                                                     run_list_arg,
                                                     client_version))
        while not run_cmd(command)['success']:
            logger.warning("Epic failure. Retrying...")
            gevent.sleep(1)

        node = chef.Node(name, api=deployment.environment.local_api)
        node.chef_environment = deployment.environment.name
        node['in_use'] = "provisioning"
        node['ipaddress'] = server.accessIPv4
        node['password'] = password
        node['uuid'] = server.id
        node['current_user'] = "root"
        node.save()
        return node

    def get_flavor(self, flavor):
        try:
            flavor_name = self.config['flavors'][flavor]
        except KeyError:
            raise Exception("Flavor not supported:{0}".format(flavor))
        return self._client_search(self.compute_client.flavors.list,
                                   "name", flavor_name, attempts=10)

    def get_image(self, image):
        try:
            image_name = self.config['images'][image]
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

    def build_instance(self, name="server", image="ubuntu", flavor="2GBP"):
        """Builds an instance with desired specs.
        :param name: name of server
        :type name: string
        :param image: desired image for server
        :type image: string
        :param flavor: desired flavor for server
        :type flavor: string
        :rtype: Server
        """
        self.config = active.config[str(self)]

        # gather attribute objects
        flavor_obj = self.get_flavor(flavor)
        image_obj = self.get_image(image)
        networks = self.get_networks()

        # build instance
        server = self.compute_client.servers.create(name, image_obj.id,
                                                    flavor_obj.id,
                                                    nics=networks)
        password = server.adminPass
        logger.info("Building: {0}".format(name))
        server = self.wait_for_state(self.compute_client.servers.get, server,
                                     "status", ["ACTIVE", "ERROR"],
                                     attempts=10)
        if server.status == "ERROR":
            logger.error("Instance entered error state. Retrying...")
            server.delete()
            return self.build_instance(name=name, image=image, flavor=flavor)
        host = server.accessIPv4
        check_port(host, 22, timeout=2)
        return server, password

    @staticmethod
    def _client_search(collection_fun, attr, desired, attempts=None,
                       interval=1):
        """Searches for a desired attribute in a list of objects.
        :param collection_fun: function to get list of objects
        :type collection_fun: function
        :param attr: attribute of object to check
        :type attr: string
        :param desired: desired value of object's attribute
        :type desired: object
        :param attempts: number of attempts to achieve state
        :type attempts: int
        :param interval: time between attempts
        :type interval: int
        :rtype: object
        """
        obj_collection = None
        attempt = 0
        in_attempt = lambda x: not attempts or attempts > x
        while in_attempt(attempt):
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

    @staticmethod
    def wait_for_state(fun, obj, attr, desired, interval=15,
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
        attempt = 0
        in_attempt = lambda x: not attempts or attempts > x
        while getattr(obj, attr) not in desired and in_attempt(attempt):
            logger.debug("Attempt: {0}/{1}".format(attempt, attempts))
            logger.info("Waiting: {0} {1}:{2}".format(obj, attr,
                                                      getattr(obj, attr)))
            gevent.sleep(interval)
            obj = fun(obj.id)
            attempt += 1
        return obj

    def power_down(self, node):
        node.run_cmd("echo 1 > /proc/sys/kernel/sysrq; "
                     "echo o > /proc/sysrq-trigger")

    def power_up(self, node):
        uuid = node['uuid']
        server = self.compute_client.servers.get(uuid)
        server.reboot("hard")

    def reload_node_list(self, node_names, api):
        return [chef.Node(node_name, api) for node_name in node_names]
