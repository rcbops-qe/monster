from time import sleep

from chef import Node, Client, Search, autoconfigure
from gevent import spawn, joinall, sleep as gsleep

from monster import util
from monster.razor_api import razor_api
from monster.server_helper import run_cmd
from monster.clients import openstack
from monster.clients.openstack import Clients


class Provisioner(object):

    def __str__(self):
        return self.__class__.__name__.lower()

    def short_name(self):
        """
        Converts to short hand name
        """
        provisioners = util.config['provisioners']
        return {value: key for key, value in provisioners.items()}[str(self)]

    def available_node(self, image, deployment):
        raise NotImplementedError

    def destroy_node(self, node):
        raise NotImplementedError


class ChefRazorProvisioner(Provisioner):
    def __init__(self, ip=None):
        self.ipaddress = ip or util.config['razor']['ip']
        self.api = razor_api(self.ipaddress)

    def provision(self, template, deployment):
        util.logger.info("Provisioning with Razor!")
        image = deployment.os_name
        return [self.available_node(image, deployment)
                for _ in template['nodes']]

    def available_node(self, image, deployment):
        """
        Provides a free node from
        """
        nodes = self.node_search("name:qa-%s-pool*" % image)
        for node in nodes:
            is_default = node.chef_environment == "_default"
            iface_in_run_list = "recipe[network-interfaces]" in node.run_list
            if (is_default and iface_in_run_list):
                node.chef_environment = deployment.environment.name
                node['in_use'] = "provisioning"
                node.save()
                return node
        deployment.destroy()
        raise Exception("No more nodes!!")

    def destroy_node(self, node):
        """
        Destroys a node provisioned by razor
        """
        cnode = Node(node.name, node.environment.local_api)
        in_use = node['in_use']
        if in_use == "provisioning" or in_use == 0:
            # Return to pool if the node is clean
            cnode['in_use'] = 0
            cnode['archive'] = {}
            cnode.chef_environment = "_default"
            cnode.save()
        else:
            # Remove active model if the node is dirty
            active_model = cnode['razor_metadata']['razor_active_model_uuid']
            try:
                if node.feature_in('controller'):
                    # rabbit can cause the node to not actually reboot
                    kill = ("for i in `ps -U rabbitmq | tail -n +2 | "
                            "awk '{print $1}' `; do kill -9 $i; done")
                    node.run_cmd(kill)
                node.run_cmd("shutdown -r now")
                self.api.remove_active_model(active_model)
                Client(node.name).delete()
                cnode.delete()
                sleep(15)
            except:
                util.logger.error("Node unreachable. "
                                  "Manual restart required:{0}".
                                  format(str(node)))

    @classmethod
    def node_search(cls, query, environment=None, tries=10):
        """
        Performs a node search query on the chef server
        """
        api = autoconfigure()
        if environment:
            api = environment.local_api
        search = None
        while not search and tries > 0:
            search = Search("node", api=api).query(query)
            sleep(10)
            tries = tries - 1
        return (n.object for n in search)


class ChefOpenstackProvisioner(Provisioner):
    def __init__(self):
        self.names = []
        self.name_index = {}
        self.creds = openstack.creds

    def name(self, name, deployment, number=None):
        """
        Helper for naming nodes
        :param name: name for node
        :type name: String
        :param deployment: deployment object
        :type deployment: Deployment
        :param number: number to append to name
        :type number: int
        :rtype: string
        """
        if name in self.name_index:
            # Name already exists, use index to name
            num = self.name_index[name] + 1
            self.name_index[name] = num
            return "{0}-{1}{2}".format(deployment, name, number=num)

        # Name doesn't exist initalize index use name
        self.name_index[name] = 1
        return "{0}-{1}".format(deployment, name)

    def provision(self, template, deployment):
        """
        Provisions a ChefNode using OpenStack
        :param template: template for cluster
        :type template: dict
        :param deployment: ChefDeployment to provision for
        :type deployment: ChefDeployment

        """
        util.logger.info("Provisioning in the cloud!")
        # acquire connection
        client = Clients().get_client(self.client_name)

        # create instances concurrently
        events = []
        for features in template['nodes']:
            name = self.name(features[0], deployment)
            self.names.append(name)
            events.append(spawn(self.chef_instance, client, deployment, name))
        joinall(events)

        # acquire chef nodes
        chef_nodes = [event.value for event in events]
        return chef_nodes

    def destroy_node(self, node):
        """
        Destroys chef node from openstack
        :param node: node to destroy
        :type node: ChefNode
        """
        cnode = Node(node.name, node.environment.local_api)
        if cnode.exists:
            compute = self.connection()
            compute.servers.get(node['uuid']).delete()
            cnode.delete()
        client = Client(node.name, node.environment.local_api)
        if client.exists:
            client.delete()

    def chef_instance(self, client, deployment, name, flavor="2GB"):
        """
        Builds an instance with desired specs and inits it with chef
        :param client: compute client object
        :type client: novaclient.client.Client
        :param deployment: deployement to add to
        :type deployment: ChefDeployment
        :param name: name for instance
        :type name: string
        :param flavor: desired flavor for node
        :type flavor: string
        :rtype: ChefNode
        """
        image = deployment.os_name
        server, password = self.build_instance(client, name=name,
                                               image=image, flavor=flavor)
        run_list = ",".join(util.config['openstack']['run_list'])
        run_list_arg = ""
        if run_list:
            run_list_arg = "-r {0}".format(run_list)
        command = 'knife bootstrap {0} -u root -P {1} -N {2} {3}'.format(
            server.accessIPv4, password, name, run_list_arg)
        run_cmd(command)
        node = Node(name, api=deployment.environment.local_api)
        node.chef_environment = deployment.environment.name
        node['in_use'] = "provisioning"
        node['ipaddress'] = server.accessIPv4
        node['password'] = password
        node['uuid'] = server.id
        node['current_user'] = "root"
        node.save()
        return node

    def build_instance(self, client, name="server", image="precise",
                       flavor="2GB"):
        """
        Builds an instance with desired specs
        :param client: compute client object
        :type client: novaclient.client.Client
        :param name: name of server
        :type name: string
        :param image: desired image for server
        :type image: string
        :param flavor: desired flavor for server
        :type flavor: string
        :rtype: Server
        """
        config = util.config['config']

        # get image
        try:
            flavor_name = config['flavors'][flavor]
        except KeyError:
            raise Exception("Flavor not supported:{0}".format(flavor))
        self._client_search(client.flavors.list, name, flavor_name,
                            attempts=10)

        # get flavor
        try:
            image_name = config['images'][image]
        except KeyError:
            raise Exception("Image not supported:{0}".format(image))
        self._client_search(client.images.list, image, image_name, attempts=10)

        # build instance
        server = client.servers.create(name, image, flavor)
        password = server.adminPass
        util.logger.info("Building:{0}".format(name))
        server = self.wait_for_state(client.servers.get, server, "status",
                                     ["ACTIVE", "ERROR"])
        return (server, password)

    def _client_search(self, collection_fun, attr, desired, attempts=None,
                       interval=1):
        obj_collection = None
        attempt = 0
        in_attempt = lambda x: not attempts or attempts > x
        while in_attempt(attempt):
            try:
                obj_collection = collection_fun()
                break
            except Exception as e:
                util.logger.error("Wait: Request error:{0}-{1}".
                                  format(desired, e))
                continue
        for obj in obj_collection:
            if getattr(obj, attr) is desired:
                return obj
        util.logger.error("Client search fail:{0} not found".format(desired))
        raise Exception("Client search fail")

    def wait_for_state(self, fun, obj, attr, desired, interval=15,
                       attempts=None):
        """
        Waits for a desired state of an object using gevented sleep
        :param fun: function to update object
        :type fun: function
        :param obj: object which to check state
        :type obj: obj
        :param attr: attribute of object of which state resides
        :type attr: str
        :param desired: desired state of attribute
        :type desired: string
        :param interval: interval to check state in secs
        :param interval: int
        :param attempts: number of attempts to acheive state
        :type attempts: int
        :rtype: obj
        """
        attempt = 0
        in_attempt = lambda x: not attempts or attempts > x
        while getattr(obj, attr) not in desired and in_attempt(attempt):
            util.logger.info("Wating:{0} {1}:{2}".format(obj, attr,
                                                         getattr(obj, attr)))
            gsleep(interval)
            obj = fun(obj.id)
            attempt = attempt + 1
        return obj


class ChefRackspaceProvisioner(ChefOpenstackProvisioner):
    def __init__(self):
        self.names = []
        self.name_index = {}
        self.creds = openstack.rax_creds
