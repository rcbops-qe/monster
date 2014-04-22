import json
import logging
import requests
import sys

from monster.nodes.util import node_search
from provisioner import Provisioner

from monster import util

logger = logging.getLogger(__name__)


class Razor2(Provisioner):
    """Provisions chef nodes in a Razor environment."""

    def __init__(self, url=None):
        self.url = url or util.config['secrets']['razor']['url']
        self.api = RazorAPI2(self.url)

    def provision(self, template, deployment):
        """Provisions a ChefNode using Razor environment.
        :param template: template for cluster
        :type template: dict
        :param deployment: ChefDeployment to provision for
        :type deployment: ChefDeployment
        :rtype: list
        """
        logger.info("Provisioning with Razor!")
        image = deployment.os_name
        self.nodes += [self.available_node(image, deployment)
                       for _ in template['nodes']]
        return self.nodes

    def available_node(self, image, deployment):
        """Provides a free node from chef pool.
        :param image: name of os image
        :type image: string
        :param deployment: ChefDeployment to add node to
        :type deployment: ChefDeployment
        :rtype: ChefNodeWrapper
        """

        # TODO: Should probably search on system name node attributes
        # Avoid specific naming of razor nodes, not portable
        nodes = node_search("name:node*")
        for node in nodes:
            is_default = node.chef_environment == "_default"
            iface_in_run_list = "recipe[rcbops-qa]" in node.run_list
            if is_default and iface_in_run_list:
                node.chef_environment = deployment.environment.name
                node['in_use'] = "provisioning"
                node.save()
                return node
        deployment.destroy()
        logger.info("Cannot build, no more available_nodes")
        sys.exit(1)

    def power_down(self, node_wrapper):
        if node_wrapper.has_feature('controller'):
            # rabbit can cause the node to not actually reboot
            kill = ("for i in `ps -U rabbitmq | tail -n +2 | "
                    "awk '{print $1}' `; do kill -9 $i; done")
            node_wrapper.run_cmd(kill)
        node_wrapper.run_cmd("shutdown -r now")

    def power_up(self, node):
        pass

    def destroy_node(self, node_wrapper):
        """Destroys a node provisioned by razor.
        :param node_wrapper: Node to destroy
        :type node_wrapper: ChefNodeWrapper
        """
        node = node_wrapper.local_node
        in_use = node_wrapper['in_use']
        if in_use == "provisioning" or in_use == 0:
            # Return to pool if the node is clean
            node['in_use'] = 0
            node['archive'] = {}
            node.chef_environment = "_default"
            node.save()
        else:
            # Reinstall node if the node is dirty
            razor_node = node.name.split("-")[0]
            try:
                if node_wrapper.has_feature('controller'):
                    # rabbit can cause the node to not actually reboot
                    kill = ("for i in `ps -U rabbitmq | tail -n +2 | "
                            "awk '{print $1}' `; do kill -9 $i; done")
                    node_wrapper.run_cmd(kill)
                node_wrapper.run_cmd("shutdown -r now")
                self.api.reinstall_node(razor_node)
                node_wrapper.client.delete()
                node.delete()
            except:
                logger.error("Node unreachable. "
                             "Manual restart required:{0}".format(str(node)))


class RazorAPI2(object):

    def __init__(self, url=None):
        """Initializer for RazorAPI class."""

        self.url = "{0}".format(url)

    def __repr__(self):
        """Print out current instance of RazorAPI."""

        outl = 'class: {0}'.format(self.__class__.__name__)
        for attr in self.__dict__:
            outl += '\n\t{0}:{1}'.format(attr, str(getattr(self, attr)))
        return outl

    def nodes(self):
        """Return all current nodes."""
        # Call the Razor RESTful API to get a list of nodes
        headers = {'content-type': 'application/json'}
        r = requests.get(
            '{0}/collections/nodes'.format(self.url), headers=headers)

        # Check the status code and return appropriately
        if r.status_code == 200:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def node(self, node):
        """Return a given node."""

        # Call the Razor RESTful API to get a node
        headers = {'content-type': 'application/json'}
        r = requests.get('{0}/collections/nodes/{1}'.format(
            self.url, node), headers=headers)

        # Check the status code and return appropriately
        if r.status_code == 200:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def reinstall_node(self, node):
        """Reinstalls a given node.
        :param node: Razor node name to reinstall
        :type node: str
        """

        # Call the Razor RESTful API to get a node
        headers = {'content-type': 'application/json'}
        data = '{{"name": "{0}"}}'.format(node)
        r = requests.post('{0}/commands/reinstall-node'.format(self.url),
                          headers=headers, data=data)

        # Check the status code and return appropriately
        if r.status_code == 202 and 'no changes' not in r.content:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))

    def delete_node(self, node):
        """Deletes a given node.
        :param node: Razor node name to destroy
        :type node: str
        """

        # Call the Razor RESTful API to get a node
        headers = {'content-type': 'application/json'}
        data = '{{"name": "{0}"}}'.format(node)
        r = requests.post('{0}/commands/delete-node'.format(self.url),
                          headers=headers, data=data)

        # Check the status code and return appropriately
        if r.status_code == 202 and 'no changes' not in r.content:
            return json.loads(r.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(r.status_code))
