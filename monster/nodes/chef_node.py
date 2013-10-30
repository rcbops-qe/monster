import traceback
from itertools import chain

from chef import Node as CNode

from monster import util
from monster.nodes.node import Node
from monster.features import node_features
from monster.provisioners import provisioner as provisioners


class ChefNode(Node):
    """
    A chef entity
    Provides chef related server fuctions
    """
    def __init__(self, ip, user, password, os, product, environment,
                 deployment, name, provisioner, branch, status=None):
        super(ChefNode, self).__init__(ip, user, password, os, product,
                                       environment, deployment, provisioner,
                                       status)
        self.name = name
        self.branch = branch
        self.run_list = []
        self.features = []

    def __str__(self):
        features = ", ".join((str(f) for f in self.features))
        node = ("Node - name:{0}, os:{1}, branch:{2}, ip:{3}, status:{4}\n\t\t"
                "Features: {5}").format(self.name, self.os_name, self.branch,
                                        self.ipaddress, self.status, features)
        return node

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
        self.save(lnode)

    def save_to_node(self):
        """
        Save deployment restore attributes to chef environment
        """
        features = [str(f).lower() for f in self.features]
        node = {'features': features,
                'status': self.status,
                'provisioner': self.provisioner.__class__.__name__.lower()}
        self['archive'] = node

    def apply_feature(self):
        """
        Runs chef client before apply features on node
        """
        self.status = "apply-feature"
        if self.run_list:
            self.run_cmd("chef-client")
        super(ChefNode, self).apply_feature()

    def save(self, chef_node=None):
        chef_node = chef_node or CNode(self.name, self.environment.local_api)
        chef_node.save(self.environment.local_api)
        if self.environment.remote_api:
            chef_node.save(self.environment.remote_api)

    def get_run_list(self):
        return CNode(self.name, self.environment.local_api).run_list

    def add_run_list_item(self, items):
        """
        Adds list of items to run_list
        """
        util.logger.debug("run_list:{0}add:{1}".format(self.run_list, items))
        self.run_list.extend(items)
        cnode = CNode(self.name, api=self.environment.local_api)
        cnode.run_list = self.run_list
        self.save(cnode)

    def add_features(self, features):
        """
        Adds a list of feature classes
        """
        util.logger.debug("node:{0} feature add:{1}".format(self.name,
                                                            features))
        classes = util.module_classes(node_features)
        for feature in features:
            feature_class = classes[feature](self)
            self.features.append(feature_class)

        # save features for restore
        self.save_to_node()

    @classmethod
    def from_chef_node(cls, node, os=None, product=None, environment=None,
                       deployment=None, provisioner=None, branch=None):
        """
        Restores node from chef node
        """
        ipaddress = node['ipaddress']
        user = node['current_user']
        password = node['password']
        name = node.name
        archive = node.get('archive', {})
        status = archive.get('status', "provisioning")
        if not provisioner:
            provisioner_name = archive.get('provisioner',
                                           "chefrazorprovisioner")
            classes = util.module_classes(provisioners)
            provisioner = classes[provisioner_name]()
        crnode = cls(ipaddress, user, password, os, product, environment,
                     deployment, name, provisioner, branch, status=status)
        try:
            crnode.add_features(archive.get('features', []))
        except:
            util.logger.error(traceback.print_exc())
            crnode.destroy()
            raise Exception("Node feature add fail{0}".format(str(crnode)))
        return crnode

    def add_tempest(self):
        if 'recipe[tempest]' not in self.get_run_list():
            self.add_run_list_item("recipe[tempest]")
            # run twice to propagate image id
            self.run_cmd("chef-client; chef-client")

        # install python requirements
        tempest_dir = util.config['tests']['tempest']['dir']
        install_cmd = "python {0}/tools/install_venv.py".format(tempest_dir)
        self.run_cmd(install_cmd)

    def test_from(self, xunit=False, tags=None, exclude=None, paths=None):
        """
        Runs tests from node
        @param xunit: Produce xunit report
        @type xunit: Boolean
        @param tags: Tags to pass the nosetests
        @type tags: list
        @param exclude: Expressions to exclude
        @param exclude: list
        @param paths: Paths to load tests from (compute, compute/servers...)
        @param paths: list
        """
        if "recipe[tempest]" not in self.get_run_list():
            util.logger.error("Tesmpest not set up on node")
            pass

        tempest_dir = util.config['tests']['tempest']['dir']

        xunit_file = "{0}.xml".format(self.name)
        xunit_flag = ''
        if xunit:
            xunit_flag = '--with-xunit --xunit-file=%s' % xunit_file

        tag_flag = "-a " + " -a ".join(tags) if tags else ""

        exclude_flag = "-e " + " -e ".join(exclude) if exclude else ''

        test_map = util.config['tests']['tempest']['test_map']
        paths = paths or set(chain(test_map.get(feature, None)
                                   for feature in
                                   self.deployment.feature_names()))
        command = ("{0}tools/with_venv.sh nosetests -w "
                   "{0}tempest/api {1} {2} {3} {4}".format(tempest_dir,
                                                           xunit_flag,
                                                           tag_flag,
                                                           paths,
                                                           exclude_flag))
        self.run_cmd(command)
        if xunit:
            self.scp_from(xunit_file, local_path=".")
            util.xunit_merge()
