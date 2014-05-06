import json
import logging
import sys

import requests

import monster.nodes.util as node_utils
import monster.provisioners.base as base
import monster.active as active

logger = logging.getLogger(__name__)


class Provisioner(base.Provisioner):
    """Provisions chef nodes in a Razor environment."""

    def __init__(self, url=None):
        self.url = url or active.config['secrets']['razor']['url']
        self.api = RazorAPI2(self.url)

    def __str__(self):
        return 'razor2'

    def provision(self, deployment):
        """Provisions nodes using Razor environment.
        :param deployment: ChefDeployment to provision for
        :type deployment: Deployment
        :rtype: list
        """
        logger.info("Provisioning with Razor!")
        image = deployment.os_name
        self.nodes += [self.available_node(image, deployment)
                       for _ in active.template['nodes']]
        return self.nodes

    def available_node(self, image, deployment):
        """Provides a free node from chef pool.
        :param image: name of os image
        :type image: string
        :param deployment: ChefDeployment to add node to
        :type deployment: Deployment
        :rtype: Node
        """

        # TODO: Should probably search on system name node attributes
        # Avoid specific naming of razor nodes, not portable
        nodes = node_utils.node_search("name:node*")
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

    def power_down(self, node):
        if node.has_feature('controller'):
            # rabbit can cause the node to not actually reboot
            kill = ("for i in `ps -U rabbitmq | tail -n +2 | "
                    "awk '{print $1}' `; do kill -9 $i; done")
            node.run_cmd(kill)
        node.run_cmd("shutdown -r now")

    def power_up(self, node):
        pass

    def destroy_node(self, node):
        """Destroys a node provisioned by Razor.
        :param node: node to destroy
        :type node: monster.nodes.chef_.node.Node
        """
        node = node.local_node
        in_use = node['in_use']
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
                if node.has_feature('controller'):
                    # rabbit can cause the node to not actually reboot
                    kill = ("for i in `ps -U rabbitmq | tail -n +2 | "
                            "awk '{print $1}' `; do kill -9 $i; done")
                    node.run_cmd(kill)
                node.run_cmd("shutdown -r now")
                self.api.reinstall_node(razor_node)
                node.client.delete()
                node.delete()
            except Exception:
                logger.error("Node unreachable. "
                             "Manual restart required:{0}".format(str(node)))


class RazorAPI2(object):

    def __init__(self, url=None):
        """Initializer for RazorAPI class."""
        self.url = str(url)

    def __repr__(self):
        outl = 'class: {0}'.format(self.__class__.__name__)
        for attr in self.__dict__:
            outl += '\n\t{0}:{1}'.format(attr, str(getattr(self, attr)))
        return outl

    def nodes(self):
        """Return all current nodes."""
        # Call the Razor RESTful API to get a list of nodes
        headers = {'content-type': 'application/json'}
        request = requests.get(
            '{0}/collections/nodes'.format(self.url), headers=headers)

        # Check the status code and return appropriately
        if request.status_code == 200:
            return json.loads(request.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(request.status_code))

    def node(self, node):
        """Return a given node."""

        # Call the Razor RESTful API to get a node
        headers = {'content-type': 'application/json'}
        request = requests.get('{0}/collections/nodes/{1}'.format(
            self.url, node), headers=headers)

        # Check the status code and return appropriately
        if request.status_code == 200:
            return json.loads(request.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(request.status_code))

    def reinstall_node(self, node):
        """Reinstalls a given node.
        :param node: Razor node name to reinstall
        :type node: str
        """

        # Call the Razor RESTful API to get a node
        headers = {'content-type': 'application/json'}
        data = '{{"name": "{0}"}}'.format(node)
        request = requests.post('{0}/commands/reinstall-node'.format(self.url),
                                headers=headers, data=data)

        # Check the status code and return appropriately
        if request.status_code == 202 and 'no changes' not in request.content:
            return json.loads(request.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(request.status_code))

    def delete_node(self, node):
        """Deletes a given node.
        :param node: Razor node name to destroy
        :type node: str
        """

        # Call the Razor RESTful API to get a node
        headers = {'content-type': 'application/json'}
        data = '{{"name": "{0}"}}'.format(node)
        request = requests.post('{0}/commands/delete-node'.format(self.url),
                                headers=headers, data=data)

        # Check the status code and return appropriately
        if request.status_code == 202 and 'no changes' not in request.content:
            return json.loads(request.content)
        else:
            return 'Error: exited with status code: {0}'.format(
                str(request.status_code))
