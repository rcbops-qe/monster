import gevent
from time import sleep
from chef import Node, Client, Search, autoconfigure
from monster import util
from monster.razor_api import razor_api


class Provisioner(object):

    def available_node(self, image, deployment):
        raise NotImplementedError

    def destroy_node(self, node):
        raise NotImplementedError


class ChefRazorProvisioner(Provisioner):
    def __init__(self, ip=None):
        self.ipaddress = ip or util.config['razor']['ip']
        self.api = razor_api(self.ipaddress)

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
        node.destroy()
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
                node.run_cmd("reboot 0")
            except:
                util.logger.error("Node unreachable:{0}".format(str(node)))
            self.api.remove_active_model(active_model)
            Client(node.name).delete()
            cnode.delete()
            sleep(15)

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


class CloudServer(Provisioner):
    def available_node(self, image, deployment):
        raise NotImplementedError

    def destroy_node(self, node):
        raise NotImplementedError

    def build_instance(self, client, name="server", image_name="precise",
                       flavor_name="1GB"):
        flavor = next(flavor.id for flavor in client.flavors.list()
                      if flavor_name in flavor.name)
        if image_name == "precise":
            image_name = "Ubuntu 12.04"
        else:
            raise Exception("Image not supported:{0}".format(image_name))
        image = next(image.id for image in client.images.list()
                     if image_name in image.name)
        server = client.servers.create(name, image, flavor)
        password = server.adminPass
        print "Building:{0}:{1}".format(server, password)
        server = self.wait_for_state(client.servers.get, server, "status",
                                     ["ACTIVE", "ERROR"])
        print server

    def wait_for_state(self, fun, obj, attr, desired, interval=10,
                       attempts=None):
        attempt = 0
        in_attempt = lambda x: not attempt or x > attempts
        while getattr(obj, attr) not in desired and in_attempt(attempt):
            print "Wating:{0} {1}:{2}".format(obj, attr, getattr(obj, attr))
            gevent.sleep(interval)
            obj = fun(obj.id)
            attempt = attempt + 1
        return obj
