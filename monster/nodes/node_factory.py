from chef import Node

from monster.provisioners.util import get_provisioner
from monster.nodes.chef_node import ChefNodeWrapper
from monster import util


class NodeFactory:
    @classmethod
    def get_chef_node(cls, node, product, environment, deployment,
                      provisioner, branch):
        """
        Restores node from chef node
        """
        remote_api = None
        if deployment:
            remote_api = deployment.environment.remote_api
        if remote_api:
            remote_node = Node(node.name, remote_api)
            if remote_node.exists:
                node = remote_node
        ip = node['ipaddress']
        user = node['current_user']
        default_pass = util.config['secrets']['default_pass']
        password = node.get('password', default_pass)
        name = node.name
        archive = node.get('archive', {})
        if not provisioner:
            provisioner_name = archive.get('provisioner', 'razor2')
            provisioner = get_provisioner(provisioner_name)
        run_list = node.run_list
        chef_remote_node = ChefNodeWrapper(name, ip, user, password, product,
                                           deployment, provisioner,
                                           environment, branch, run_list)
        chef_remote_node.add_features(archive.get('features', []))
        return chef_remote_node
