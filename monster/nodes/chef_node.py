from chef import Node

from monster import util
from monster.nodes.basenode import BaseNode


class ChefNode(BaseNode):
    """
    A Chef entity
    Provides chef related server functions
    """
    def __init__(self, name, ip, user, password, product, deployment,
                 provisioner, environment, branch, run_list=None):
        super(ChefNode, self).__init__(name, ip, user, password, product,
                                       deployment, provisioner)
        self.environment = environment
        self.branch = branch
        self.run_list = run_list or []

    def __str__(self):
        features = ", ".join(self.feature_names)
        node = ("Node - name:{0}, os:{1}, branch:{2}, ip:{3}, status:{4}\n\t\t"
                "Features: {5}").format(self.name, self.os_name, self.branch,
                                        self.ipaddress, self.status, features)
        return node

    def __getitem__(self, item):
        """
        Node has access to chef attributes
        """
        util.logger.debug("getting {0} on {1}".format(item, self.name))
        return Node(self.name, api=self.environment.local_api)[item]

    def __setitem__(self, item, value):
        """
        Node can set chef attributes
        """
        util.logger.debug("setting {0} to {1} on {2}".format(item, value,
                                                             self.name))
        lnode = Node(self.name, api=self.environment.local_api)
        lnode[item] = value
        self.save(lnode)

    def build(self):
        """ Builds the node
        """

        # clear run_list
        self.run_list = []
        node = Node(self.name, self.environment.local_api)
        node.run_list = []
        node.save()
        super(ChefNode, self).build()

    def upgrade(self, times=1, accept_failure=False):
        """
        Upgrade the node according to its features
        :param times: number of times to run chef-client
        :type times: int
        :param accept_failure: whether to accept failure of chef-client runs
        :type accept_failure: boolean
        """
        self.branch = self.deployment.branch
        super(ChefNode, self).upgrade()
        if not self.feature_in("chefserver"):
            try:
                self.run(times=times)
            except Exception as e:
                if accept_failure:
                    pass
                else:
                    raise Exception("chef-client upgrade failure:{0}".
                                    format(e))

    def apply_feature(self):
        """
        Runs chef client before apply features on node
        """
        self.status = "apply-feature"
        if not self.feature_in("chefserver"):
            self.run()
        super(ChefNode, self).apply_feature()

    def save(self, chef_node=None):
        """
        Saves a chef node to local and remote chef server
        """
        util.logger.debug("Saving chef_node:{0}".format(self.name))
        chef_node = chef_node or Node(self.name, self.environment.local_api)
        chef_node.save(self.environment.local_api)
        if self.environment.remote_api:
            # syncs to remote chef server if available
            chef_node.save(self.environment.remote_api)

    def save_locally(self, chef_node=None):
        """
        Syncs the remote chef nodes attribute to the local chef server
        """
        util.logger.debug("Syncing chef node from remote:{0}".format(
            self.name))
        if self.environment.remote_api:
            chef_node = chef_node or Node(self.name,
                                          self.environment.remote_api)
            chef_node.save(self.environment.local_api)

    def get_run_list(self):
        return Node(self.name, self.environment.local_api).run_list

    def add_run_list_item(self, items):
        """
        Adds list of items to run_list
        """
        util.logger.debug("run_list:{0} add:{1}".format(self.run_list, items))
        self.run_list.extend(items)
        cnode = Node(self.name, api=self.environment.local_api)
        cnode.run_list = self.run_list
        self.save(cnode)

    def remove_run_list_item(self, item):
        """
        Adds list of items to run_list
        """
        util.logger.debug("run_list:{0} remove:{1}".format(self.run_list,
                                                           item))
        self.run_list.pop(self.run_list.index(item))
        cnode = Node(self.name, api=self.environment.local_api)
        cnode.run_list = self.run_list
        self.save(cnode)

    def run(self, times=1, debug=True, accept_failure=True):
        cmd = util.config['chef']['client']['run_cmd']
        for i in xrange(times):
            if debug:
                time = self.run_cmd("date +%F_%T")['return'].rstrip()
                log_file = '{0}-client-run.log'.format(time)
                cmd = '{0} -l debug -L "/opt/chef/{1}"'.format(cmd, log_file)
            chef_run = self.run_cmd(cmd)
            self.save_locally()
            if not chef_run['success'] and not accept_failure:
                raise Exception("Chef client failure")
