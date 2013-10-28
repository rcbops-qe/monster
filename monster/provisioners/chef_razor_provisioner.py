from time import sleep

from chef import Node, Client

from monster import util
from monster.provisioners.provisioner import Provisioner
from monster.razor_api import razor_api


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
                node['in_use'] = "provisioned"
                node.save()
                return node
        self.destroy()
        raise Exception("No more nodes!!")

    def destroy_node(self, node):
        """
        Destroys a node provisioned by razor
        """
        cnode = Node(node.name)
        if self['in_use'] == "provisioned":
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
            Client(self.name).delete()
            cnode.delete()
            sleep(15)
