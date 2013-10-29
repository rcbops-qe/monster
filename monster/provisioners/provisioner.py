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
        cnode = Node(node.name)
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
