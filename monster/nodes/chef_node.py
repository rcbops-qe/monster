import logging

from chef import Node as ChefNode

from monster import util
from monster.nodes.node import Node
from monster.features import node as node_features
from monster.provisioners.util import get_provisioner

logger = logging.getLogger(__name__)


class Chef(Node):
    """
    A chef entity
    Provides chef related server fuctions
    """
    def __init__(self, ip, user, password, product, environment, deployment,
                 name, provisioner, branch, status=None, run_list=None):
        super(Chef, self).__init__(ip, user, password, product, environment,
                                   deployment, provisioner, status)
        self.name = name
        self.branch = branch
        self.run_list = run_list or []
        self.features = []

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
        logger.debug("getting {0} on {1}".format(item, self.name))
        return ChefNode(self.name, api=self.environment.local_api)[item]

    def __setitem__(self, item, value):
        """
        Node can set chef attributes
        """
        logger.debug("setting {0} to {1} on {2}".format(item, value,
                                                        self.name))
        lnode = ChefNode(self.name, api=self.environment.local_api)
        lnode[item] = value
        self.save(lnode)

    def build(self):
        """ Builds the node
        """

        # clear run_list
        self.run_list = []
        node = ChefNode(self.name, self.environment.local_api)
        node.run_list = []
        node.save()
        super(Chef, self).build()

    def upgrade(self, times=1, accept_failure=False):
        """
        Upgrade the node according to its features
        :param times: number of times to run chef-client
        :type times: int
        :param accept_failure: whether to accept failure of chef-client runs
        :type accept_failure: boolean
        """
        self.branch = self.deployment.branch
        super(Chef, self).upgrade()
        if not self.feature_in("chefserver"):
            try:
                self.run(times=times)
            except Exception as e:
                if accept_failure:
                    pass
                else:
                    raise Exception("chef-client upgrade failure:{0}".
                                    format(e))

    def save_to_node(self):
        """
        Save deployment restore attributes to chef environment
        """
        features = [str(f).lower() for f in self.features]
        node = {'features': features,
                'status': self.status,
                'provisioner': str(self.provisioner)}
        self['archive'] = node

    def apply_feature(self):
        """
        Runs chef client before apply features on node
        """
        self.status = "apply-feature"
        if not self.feature_in("chefserver"):
            self.run()
        super(Chef, self).apply_feature()

    def save(self, chef_node=None):
        """
        Saves a chef node to local and remote chef server
        """
        logger.debug("Saving chef_node:{0}".format(self.name))
        chef_node = chef_node or ChefNode(self.name,
                                          self.environment.local_api)
        chef_node.save(self.environment.local_api)
        if self.environment.remote_api:
            # syncs to remote chef server if available
            chef_node.save(self.environment.remote_api)

    def save_locally(self, chef_node=None):
        """
        Syncs the remote chef nodes attribute to the local chef server
        """
        logger.debug("Syncing chef node from remote:{0}".format(
            self.name))
        if self.environment.remote_api:
            chef_node = chef_node or ChefNode(self.name,
                                              self.environment.remote_api)
            chef_node.save(self.environment.local_api)

    def get_run_list(self):
        return ChefNode(self.name, self.environment.local_api).run_list

    def add_run_list_item(self, items):
        """
        Adds list of items to run_list
        """
        logger.debug("run_list:{0} add:{1}".format(self.run_list, items))
        self.run_list.extend(items)
        cnode = ChefNode(self.name, api=self.environment.local_api)
        cnode.run_list = self.run_list
        self.save(cnode)

    def remove_run_list_item(self, item):
        """
        Adds list of items to run_list
        """
        logger.debug("run_list:{0} remove:{1}".format(self.run_list,
                                                      item))
        self.run_list.pop(self.run_list.index(item))
        cnode = ChefNode(self.name, api=self.environment.local_api)
        cnode.run_list = self.run_list
        self.save(cnode)

    def add_features(self, features):
        """
        Adds a list of feature classes
        """
        logger.debug("node:{0} feature add:{1}".format(self.name,
                                                       features))
        classes = util.module_classes(node_features)
        for feature in features:
            feature_class = classes[feature](self)
            self.features.append(feature_class)

        # save features for restore
        self.save_to_node()

    @classmethod
    def from_chef_node(cls, node, product=None, environment=None,
                       deployment=None, provisioner=None, branch=None):
        """
        Restores node from chef node
        """
        remote_api = None
        if deployment:
            remote_api = deployment.environment.remote_api
        if remote_api:
            rnode = ChefNode(node.name, remote_api)
            if rnode.exists:
                node = rnode
        ipaddress = node['ipaddress']
        user = node['current_user']
        default_pass = util.config['secrets']['default_pass']
        password = node.get('password', default_pass)
        name = node.name
        archive = node.get('archive', {})
        status = archive.get('status', "provisioning")
        if not provisioner:
            provisioner_name = archive.get('provisioner', "razor2")
            provisioner = get_provisioner(provisioner_name)
        run_list = node.run_list
        crnode = cls(ipaddress, user, password, product, environment,
                     deployment, name, provisioner, branch,
                     status=status, run_list=run_list)
        crnode.add_features(archive.get('features', []))
        return crnode

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
