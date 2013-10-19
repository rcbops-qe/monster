"""
Provides classes of nodes (server entities)
"""

import types
from monster import util
from time import sleep
from chef import Node as CNode
from chef import Client as CClient
import monster.Features.Node as node_features
from inspect import getmembers, isclass
from monster.server_helper import ssh_cmd, scp_to, scp_from


class Node(object):
    """
    A individual computation entity to deploy a part OpenStack onto
    Provides server related functions
    """
    def __init__(self, ip, user, password, os, product, environment,
                 deployment, status="provisioning"):
        self.ipaddress = ip
        self.user = user
        self.password = password
        self.os = os
        self.product = product
        self.environment = environment
        self.deployment = deployment
        self.features = []
        self._cleanups = []
        self.status = status

    def __repr__(self):
        """ Print out current instance
        """
        outl = 'class: ' + self.__class__.__name__
        for attr in self.__dict__:
            # We want to not print the deployment because
            # it is a circular reference
            if attr not in ['deployment', 'password']:
                if attr == 'features':
                    features = "\tFeatures: {0}".format(
                        ", ".join(map(str, self.features)))
                elif isinstance(getattr(self, attr), types.NoneType):
                    outl += '\n\t{0} : {1}'.format(attr, 'None')
                else:
                    outl += '\n\t{0} : {1}'.format(attr, getattr(self, attr))
            outl += '\n\tIP : {1}'.format(self.ipaddress)

        return "\n".join([outl, features])

    def run_cmd(self, remote_cmd, user=None, password=None, quiet=False):
        """
        Runs a command on the node
        """
        user = user or self.user
        password = password or self.password
        util.logger.info("Running: {0} on {1}".format(remote_cmd, self.name))
        return ssh_cmd(self.ipaddress, remote_cmd=remote_cmd, user=user,
                       password=password, quiet=quiet)

    def scp_to(self, local_path, user=None, password=None, remote_path=""):
        """
        Sends a file to the node
        """
        user = user or self.user
        password = password or self.password
        return scp_to(self.ipaddress, local_path, user=user, password=password,
                      remote_path=remote_path)

    def scp_from(self, remote_path, user=None, password=None, local_path=""):
        """
        Retreives a file from the node
        """
        user = user or self.user
        password = password or self.password
        return scp_from(self.ipaddress, remote_path, user=user,
                        password=password, local_path=local_path)

    def pre_configure(self):
        """Pre configures node for each feature"""
        self.status = "pre-configure"
        for feature in self.features:
            log = "Node feature: pre-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.pre_configure()

    def apply_feature(self):
        self.status = "apply-feature"
        """Applies each feature"""
        for feature in self.features:
            log = "Node feature: update environment: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.apply_feature()

    def post_configure(self):
        """Post configures node for each feature"""
        self.status = "post-configure"
        for feature in self.features:
            log = "Node feature: post-configure: {0}"\
                .format(str(feature))
            util.logger.debug(log)
            feature.post_configure()

    def build(self):
        """Runs build steps for node's features"""
        self['in_use'] = ",".join(map(str, self.features))
        self.pre_configure()
        self.apply_feature()
        self.post_configure()
        self.status = "done"

    def destroy(self):
        """
        Destroy interface
        """
        raise NotImplementedError


class ChefRazorNode(Node):
    """
    A chef entity
    Provides chef related server fuctions
    """
    def __init__(self, ip, user, password, os, product, environment,
                 deployment, name, provisioner, branch, status="provisioning"):
        super(ChefRazorNode, self).__init__(ip, user, password, os, product,
                                            environment, deployment, status)
        self.name = name
        self.razor = provisioner
        self.branch = branch
        self.run_list = []
        self.features = []

    def save_to_node(self):
        """
        Save deployment restore attributes to chef environment
        """
        node = {'features': self.features,
                'status': self.status}
        self.environment.add_override_attr('node', node)

    def apply_feature(self):
        """
        Runs chef client before apply features on node
        """
        self.status = "apply-feature"
        if self.run_list:
            self.run_cmd("chef-client")
        super(ChefRazorNode, self).apply_feature()

    def add_run_list_item(self, items):
        """
        Adds list of items to run_list
        """
        util.logger.debug("run_list:{0}add:{1}".format(self.run_list, items))
        self.run_list.extend(items)
        cnode = CNode(self.name)
        cnode.run_list = self.run_list
        cnode.save()

    def __getitem__(self, item):
        """
        Node has access to chef attributes
        """
        return CNode(self.name, api=self.environment.local_api)[item]

    def __setitem__(self, item, value):
        """
        Node can set chef attributes
        """
        util.logger.debug("setting {0} to {1} on {2}".format(item, value,
                                                             self.name))
        lnode = CNode(self.name, api=self.environment.local_api)
        lnode[item] = value
        lnode.save()
        if self.environment.remote_api:
            rnode = CNode(self.name, api=self.environment.remote_api)
            rnode[item] = value
            rnode.save()

    def destroy(self):
        """
        Destroys node resets attributes if clean restores razor image if dirty
        """
        self.status = "Destroying"
        util.logger.info("Destroying node:{0}".format(self.name))
        cnode = CNode(self.name)
        if self['in_use'] == "provisioned":
            # Return to pool if the node is clean
            cnode['in_use'] = 0
            cnode['node'] = {}
            cnode.chef_environment = "_default"
            cnode.save()
        else:
            # Remove active model if the node is dirty
            active_model = cnode['razor_metadata']['razor_active_model_uuid']
            self.run_cmd("reboot 0")
            self.razor.remove_active_model(active_model)
            CClient(self.name).delete()
            cnode.delete()
            sleep(15)
        self.status = "Destroyed"

    def add_features(self, features):
        """
        Adds a list of feature classes
        """
        classes = {k.lower(): v for (k, v) in
                   getmembers(node_features, isclass)}
        for feature in features:
            feature_class = classes[feature](self)
            self.features.append(feature_class)

        # save features for restore
        self.save_to_node()

    @classmethod
    def from_chef_node(cls, node, os, product, environment, deployment,
                       provisioner, branch):
        """
        Restores node from chef node
        """
        ip = node['ipaddress']
        user = node['current_user']
        password = node['password']
        name = node.name
        archive = node.get('node', {})
        status = archive.get('status', "provisioning")
        crnode = cls(ip, user, password, os, product, environment, deployment,
                     name, provisioner, branch, status=status)
        crnode.add_features(archive.get('features', []))
        return crnode
