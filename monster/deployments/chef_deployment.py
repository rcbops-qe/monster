import os
from time import sleep

from chef import autoconfigure, Environment, Node

from monster import util
from monster.Environments import Chef
from monster.config import Config
from monster.deployments.deployment import Deployment
from monster.features import deployment_features
from monster.features.node_features import ChefServer
from monster.nodes.chef_node import ChefNode
from monster.provisioners import provisioner as provisioners
from monster.provisioners.provisioner import ChefRazorProvisioner
from monster.clients.openstack import Creds, Clients


class ChefDeployment(Deployment):
    """
    Deployment mechinisms specific to deployment using
    Opscode's Chef as configuration management
    """

    def __init__(self, name, os_name, branch, environment, provisioner,
                 status=None, product=None, clients=None):
        status = status or "provisioning"
        super(ChefDeployment, self).__init__(name, os_name, branch,
                                             provisioner, status, product,
                                             clients)
        self.environment = environment
        self.has_controller = False

    def __str__(self):
        nodes = "\n\t".join(str(node) for node in self.nodes)
        features = ", ".join(self.feature_names())
        deployment = ("Deployment - name:{0}, os:{1}, branch:{2}, status:{3}\n"
                      "{4}\nFeatures: \n\t{5}\n"
                      "Nodes: \n\t{6}".format(self.name, self.os_name,
                                              self.branch, self.status,
                                              self.environment, features,
                                              nodes))
        return deployment

    def save_to_environment(self):
        """
        Save deployment restore attributes to chef environment
        """
        features = {key: value for (key, value) in
                    ((str(x).lower(), x.rpcs_feature) for x in self.features)}
        nodes = [n.name for n in self.nodes]
        deployment = {'nodes': nodes,
                      'features': features,
                      'name': self.name,
                      'os_name': self.os_name,
                      'branch': self.branch,
                      'status': self.status,
                      'product': self.product,
                      'provisioner': self.provisioner.short_name()}
        self.environment.add_override_attr('deployment', deployment)

    def build(self):
        """
        Saves deployment for restore after build
        """
        super(ChefDeployment, self).build()
        self.save_to_environment()

    def prepare_upgrade(self):
        # 4.2.1 Upgrade procedures
        chef_server = next(self.search_role('chefserver'))

        munge = ["for i in /var/chef/cache/cookbooks/*; do rm -rf $i; done"]
        cmds = []
        if self.os_name == "precise":
            cmds = ["apt-get -y install python-warlock python-novaclient babel",
                    "apt-get -y install openstack-dashboard python-django-horizon"]
            munge.extend(["apt-get -y install python-dev",
                          "apt-get -y install python-setuptools"])

            provisioner = self.provisioner.short_name
            if provisioner == "rackspace" or provisioner == "openstack":
                cmds.extend(
                    ["apt-get update",
                     "apt-get remove qemu-utils",
                     "apt-get install qemu-utils"])

        if self.os_name == "centos":
            munge.extend(["yum install -y openssl-devel"
                          "yum install -y python-devel",
                          "yum install -y python-setuptools"])
        commands = "; ".join(cmds)
        controllers = list(self.search_role('controller'))
        computes = list(self.search_role('compute'))
        for node in controllers:
            node.run_cmd(commands)
        for node in computes:
            node.run_cmd(commands)

        munge.extend(["rm -rf /opt/upgrade/mungerator",
                      "git clone https://github.com/rcbops/mungerator /opt/upgrade/mungerator",
                      "python /opt/upgrade/mungerator/setup.py install",
                      "mungerator munger --client-key /etc/chef-server/admin.pem --auth-url https://127.0.0.1:4443 all-nodes-in-env --name {0}".format(self.name)])
        chef_server.run_cmd("; ".join(munge))
        self.environment.save_locally()

        # Delete quantum haproxy config
        cmd = "rm -rf /etc/haproxy/haproxy.d/vs_quantum-api.cfg"
        controllers[0].run_cmd(cmd)

    def upgrade(self, upgrade_branch):
        """
        Upgrades the deployment (very chefy, rcbopsy)
        """

        # Gather all the nodes of the deployment
        chef_server = next(self.search_role('chefserver'))
        controllers = list(self.search_role('controller'))
        computes = list(self.search_role('compute'))

        # upgrade the chef server
        old_branch = self.branch
        self.branch = upgrade_branch
        if "4.2.1" in upgrade_branch:
            self.prepare_upgrade()
        chef_server.upgrade()
        controller1 = controllers[0]
        image_upload = None
        if self.feature_in('highavailability'):
            # save image upload value
            override = self.environment.override_attributes
            try:
                image_upload = override['glance']['image_upload']
                override['glance']['image_upload'] = False
                self.environment.save()
            except KeyError:
                pass

            controller2 = controllers[1]
            stop = """for i in `monit status | grep Process | awk '{print $2}' | grep -v mysql | sed "s/'//g"`; do monit stop $i; done"""
            start = """for i in `monit status | grep Process | awk '{print $2}' | grep -v mysql | sed "s/'//g"`; do monit start $i; done"""
            keep_stop = "service keepalived stop"
            controller2.run_cmd(keep_stop)
            # Sleep for vips to move
            sleep(10)
            controller2.run_cmd(stop)
            # Sleeping for monit to stop services
            sleep(30)
            # Upgrade
            if "4.1.3" in upgrade_branch:
                controller1.upgrade(times=2, accept_failure=True)
                controller1.run_cmd("service keepalived restart")
            controller1.upgrade()
            controller2.upgrade()
            controller2.run_cmd(start)
        controller1.upgrade()

        if image_upload:
            override['glance']['image_upload'] = image_upload
            self.environment.save()

        for compute in computes:
            compute.upgrade()

        if "4.2.1" in upgrade_branch:
            if self.feature_in("neutron"):
                cmds = ["apt-get update",
                        "apt-get install python-cmd2 python-pyparsing"]
                cmd = "; ".join(cmds)
                for controller in controllers:
                    controller.run_cmd(cmd)
                for compute in computes:
                    compute.run_cmd(cmd)

    def update_environment(self):
        """
        Saves deployment for restore after update environment
        """
        super(ChefDeployment, self).update_environment()
        self.save_to_environment()

    @classmethod
    def fromfile(cls, name, template_name, branch, provisioner, template_file,
                 template_path=None):
        """
        Returns a new deployment given a deployment template at path
        :param name: name for the deployment
        :type name: string
        :param name: name of template to use
        :type name: string
        :param branch: branch of the RCBOPS chef cookbook repo to use
        :type branch:: string
        :param provisioner: provisioner to use for nodes
        :type provisioner: Provisioner
        :param path: path to template
        :type path: string
        :rtype: ChefDeployment
        """
        local_api = autoconfigure()

        if Environment(name, api=local_api).exists:
            # Use previous dry build if exists
            util.logger.info("Using previous deployment:{0}".format(name))
            return cls.from_chef_environment(name)

        if not template_path:
            path = os.path.join(os.path.dirname(__file__),
                                os.pardir, os.pardir,
                                'deployment_templates/{0}.yaml'.format(
                                    template_file))
        else:
            path = template_path

        template = Config(path)[template_name]

        environment = Chef(name, local_api, description=name)

        os_name = template['os']
        product = template['product']

        deployment = cls.deployment_config(template['features'], name, os_name,
                                           branch, environment, provisioner,
                                           product=product)

        # provision nodes
        chef_nodes = provisioner.provision(template, deployment)
        for node in chef_nodes:
            cnode = ChefNode.from_chef_node(node, os_name, product,
                                            environment, deployment,
                                            provisioner, branch)
            provisioner.post_provision(cnode)
            deployment.nodes.append(cnode)

        # add features
        for node, features in zip(deployment.nodes, template['nodes']):
            node.add_features(features)

        return deployment

    @classmethod
    def from_chef_environment(cls, environment):
        """
        Rebuilds a Deployment given a chef environment
        :param environment: name of environment
        :type environment: string
        :rtype: ChefDeployment
        """

        local_api = autoconfigure()
        env = Environment(environment, api=local_api)
        override = env.override_attributes
        default = env.default_attributes
        chef_auth = override.get('remote_chef', None)
        remote_api = None
        if chef_auth:
            remote_api = ChefServer._remote_chef_api(chef_auth)
            renv = Environment(environment, api=remote_api)
            override = renv.override_attributes
            default = renv.default_attributes
        environment = Chef(env.name, local_api, description=env.name,
                           default=default, override=override,
                           remote_api=remote_api)

        name = env.name
        deployment_args = override.get('deployment', {})
        features = deployment_args.get('features', {})
        os_name = deployment_args.get('os_name', None)
        branch = deployment_args.get('branch', None)
        status = deployment_args.get('status', "provisioning")
        product = deployment_args.get('product', None)
        provisioner_name = deployment_args.get('provisioner', "razor")
        provisioner_class_name = util.config["provisioners"][provisioner_name]
        provisioner = util.module_classes(provisioners)[
            provisioner_class_name]()

        deployment = cls.deployment_config(features, name, os_name, branch,
                                           environment, provisioner, status,
                                           product=product)

        nodes = deployment_args.get('nodes', [])
        for node in (Node(n, local_api) for n in nodes):
            if not node.exists:
                util.logger.error("Non existant chef node:{0}".
                                  format(node.name))
                continue
            cnode = ChefNode.from_chef_node(node, deployment_args['os_name'],
                                            product, environment, deployment,
                                            provisioner,
                                            deployment_args['branch'])
            deployment.nodes.append(cnode)
        return deployment

    @classmethod
    def deployment_config(cls, features, name, os_name, branch, environment,
                          provisioner, status=None, product=None):
        """
        Returns deployment given dictionaries of features
        :param features: dictionary of features {"monitoring": "default", ...}
        :type features: dict
        :param name: name of deployment
        :type name: string
        :param os_name: name of operating system
        :type os_name: string
        :param branch: branch of rcbops chef cookbooks to use
        :type branch: string
        :param environment: ChefEnvironment for deployment
        :type environment: ChefEnvironment
        :param provisioner: provisioner to deploy nodes
        :type provisioner: Provisioner
        :param status: initial status of deployment
        :type status: string
        :param product: name of rcbops product - compute, storage
        :type product: string
        :rtype: ChefDeployment
        """
        status = status or "provisioning"
        deployment = cls(name, os_name, branch, environment,
                         provisioner, status, product)
        deployment.add_features(features)
        return deployment

    def add_features(self, features):
        """
        Adds a dictionary of features to deployment
        :param features: dictionary of features {"monitoring": "default", ...}
        :type features: dict
        """
        # stringify and lowercase classes in deployment features
        classes = util.module_classes(deployment_features)
        for feature, rpcs_feature in features.items():
            util.logger.debug("feature: {0}, rpcs_feature: {1}".format(
                feature, rpcs_feature))
            self.features.append(classes[feature](self, rpcs_feature))

    def destroy(self):
        """
        Destroys Chef Deployment
        """
        self.status = "Destroying"
        # Nullify remote api so attributes are not sent remotely
        self.environment.remote_api = None
        super(ChefDeployment, self).destroy()
        # Destroy rogue nodes
        if not self.nodes:
            nodes = ChefRazorProvisioner.node_search("chef_environment:{0}".
                                                     format(self.name),
                                                     tries=1)
            for n in nodes:
                ChefNode.from_chef_node(n, environment=self.environment).\
                    destroy()

        # Destroy Chef environment
        self.environment.destroy()
        self.status = "Destroyed"

    def openrc(self):
        """
        Opens a new shell with variables loaded for novaclient
        """
        user_name = self.environment.override_attributes['keystone'][
            'admin_user']
        user = self.environment.override_attributes['keystone']['users'][
            user_name]
        password = user['password']
        tenant = user['roles'].keys()[0]
        controller = next(self.search_role('controller'))
        url = Node(controller.name).normal['keystone']['publicURL']
        strategy = 'keystone'
        openrc = {'OS_USERNAME': user_name, 'OS_PASSWORD': password,
                  'OS_TENANT_NAME': tenant, 'OS_AUTH_URL': url,
                  'OS_AUTH_STRATEGY': strategy, 'OS_NO_CACHE': '1'}
        for key in openrc.keys():
            os.putenv(key, openrc[key])
        os.system(os.environ['SHELL'])

    def horizon_ip(self):
        """
        Returns ip of horizon
        :rtype: string
        """
        controller = next(self.search_role('controller'))
        ip = controller.ipaddress
        if "vips" in self.environment.override_attributes:
            ip = self.environment.override_attributes['vips']['nova-api']
        return ip

    def openstack_clients(self):
        """
        Setup openstack clients generator for deployment
        """
        override = self.environment.override_attributes
        keystone = override['keystone']
        users = keystone['users']
        user = keystone['admin_user']
        region = "RegionOne"
        apikey = users[user]["password"]
        auth_url = "http://{0}:5000/v2.0".format(self.horizon_ip())
        creds = Creds(user=user, apikey=apikey, region=region,
                      auth_url=auth_url)
        self.clients = Clients(creds)
