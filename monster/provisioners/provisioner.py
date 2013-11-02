import gevent
from time import sleep

from chef import Node, Client, Search, autoconfigure

import novaclient.auth_plugin
from novaclient.client import Client as NovaClient

from monster import util
from monster.nodes.chef_node import ChefNode
from monster.razor_api import razor_api
from monster.server_helper import run_cmd


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


class ChefCloudServer(Provisioner):
    def __init__(self):
        self.names = {}

    def provision(self, template, deployment):
        client = self.connection()
        events = [
            gevent.spawn(self.chef_instance, client, features, deployment)
            for features in template['nodes']
        ]
        gevent.joinall(events)
        chef_nodes = [Node(features[0]) for features in template['nodes']]
        product = template['product']
        os_name = deployment.os_name
        environment = deployment.environment
        provisioner = self
        branch = deployment.branch
        monster_nodes = [
            ChefNode.from_chef_node(node, os_name, product, environment,
                                    deployment, provisioner, branch)
            for node in chef_nodes]
        deployment.nodes.extend(monster_nodes)

    def destroy_node(self, node):
        cnode = Node(node.name, node.environment.local_api).destroy()
        compute = self.connection()
        compute.get(node['uuid']).delete()
        cnode.destroy()
        Client(node.name, node.environment.local_api).destroy()

    def chef_instance(self, client, features, deployment, flavor="1GB"):
        name = features[0]
        image = deployment.os_name
        server, password = self.build_instance(client, name=name,
                                               image=image, flavor=flavor)
        command = 'knife bootstrap {0} -u root -P {1} -N'.format(
            self.server.accessIPv4, password, name)
        run_cmd(command)
        node = Node(name, api=deployment.environment.local_api)
        node['password'] = password
        node['uuid'] = server.id
        node.save()

    def build_instance(self, client, name="server", image="precise",
                       flavor="1GB"):
        openstack = util.config['openstack']
        try:
            flavor_name = openstack['flavors'][flavor]
        except KeyError:
            raise Exception("Flavor not supported:{0}".format(flavor))
        flavor = next(flavor.id for flavor in client.flavors.list()
                      if flavor_name in flavor.name)
        try:
            image_name = openstack['iamges'][image]
        except KeyError:
            raise Exception("Image not supported:{0}".format(image))
        image = next(image.id for image in client.images.list()
                     if image_name in image.name)
        server = client.servers.create(name, image, flavor)
        password = server.adminPass
        util.logger.info("Building:{0}".format(name))
        server = self.wait_for_state(client.servers.get, server, "status",
                                     ["ACTIVE", "ERROR"])
        return (server, password)

    def wait_for_state(self, fun, obj, attr, desired, interval=10,
                       attempts=None):
        attempt = 0
        in_attempt = lambda x: not attempts or x > attempts
        while getattr(obj, attr) not in desired and in_attempt(attempt):
            print "Wating:{0} {1}:{2}".format(obj, attr, getattr(obj, attr))
            gevent.sleep(interval)
            obj = fun(obj.id)
            attempt = attempt + 1
        return obj

    def connection():
        creds = util.config['secrets']['openstack']
        plugin = creds['plugin']
        if plugin:
            novaclient.auth_plugin.discover_auth_systems()
            auth_plugin = novaclient.auth_plugin.load_plugin("rackspace")
        user = creds['user']
        api_key = creds['api_key']
        auth_url = creds['auth_url']
        region = creds['region']
        compute = NovaClient('1.1', user, api_key, user, auth_url=auth_url,
                             region_name=region, service_type='compute',
                             os_cache=False, no_cache=True,
                             auth_plugin=auth_plugin, auth_system=plugin,
                             insecure=True)
        return compute
